"""Bounded HTTP and lossless JSON. GET retries only; token POSTs are never replayed."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import random
import time

import httpx2 as httpx
import simplejson as json

MAX_BYTES = 8 * 1024 * 1024


class OuraError(Exception):
    def __init__(self, code, retry_after=None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)  # Never copy provider bodies, URLs or credentials.


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw, use_decimal=True, object_pairs_hook=unique_pairs,
                          allow_nan=False)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise OuraError('invalid_response') from None


def encode(value):
    return json.dumps(value, use_decimal=True, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def retry_delay(header, attempt):
    if header:
        try:
            delay = float(header)
        except ValueError:
            try:
                when = parsedate_to_datetime(header)
                if when.tzinfo is None:
                    raise ValueError
                delay = (when - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = None
        if delay is not None and not math.isnan(delay) and delay >= 0:
            return delay
    return 2 ** attempt + random.uniform(0, 0.5)


def request(method, url, *, token=None, body=None, credentials=None, client=None):
    """Fixed endpoint URLs supplied only by our catalog, never provider next_token URLs."""
    own = client is None
    client = client or httpx.Client(timeout=10, follow_redirects=False, trust_env=False)
    try:
        for attempt in range(3 if method == 'GET' else 1):
            headers = {'Accept': 'application/json', 'User-Agent': 'PrivateHealthDashboard/1.0',
                       'Accept-Encoding': 'identity'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            if body is not None:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            auth = httpx.BasicAuth(*credentials) if credentials else None
            try:
                started = time.monotonic()
                with client.stream(method, url, headers=headers, content=body, auth=auth) as response:
                    status = response.status_code
                    wait_header = response.headers.get('Retry-After')
                    if status == 200:
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > (65536 if method == 'POST' else MAX_BYTES) or time.monotonic() - started > 20:
                                raise OuraError('response_limit')
                            chunks.append(chunk)
                        try:
                            raw = b''.join(chunks).decode('utf-8')
                        except UnicodeError:
                            raise OuraError('invalid_response') from None
                        parsed = decode(raw)
                        if not isinstance(parsed, dict):
                            raise OuraError('invalid_response')
                        return parsed, raw
                    # Never log/reflect error bodies, nor follow redirects with tokens.
                    if method != 'GET':
                        raise OuraError('token_exchange_failed')
                    if status == 401:
                        # Some Oura scope failures use 401. Inspect only a bounded
                        # error fragment, classify it, and never return its contents.
                        error_bytes = bytearray()
                        for chunk in response.iter_bytes():
                            error_bytes.extend(chunk[:2049-len(error_bytes)])
                            if len(error_bytes) > 2048 or time.monotonic()-started > 20:
                                break
                        try:
                            error = decode(bytes(error_bytes))
                            hint = str(error.get('error', ''))+' '+str(error.get('detail', ''))
                            if 'scope' in hint.lower():
                                raise OuraError('permission_or_membership')
                        except (AttributeError, UnicodeError):
                            pass
                        except OuraError as error:
                            if error.code == 'permission_or_membership':
                                raise
                        raise OuraError('unauthorized')
                    if status not in {429, 500, 502, 503, 504}:
                        raise OuraError({401: 'unauthorized', 403: 'permission_or_membership',
                                         404: 'category_unavailable'}.get(status, 'provider_rejected'))
                    delay = retry_delay(wait_header, attempt)
            except (httpx.TransportError, OSError):
                if method != 'GET':
                    raise OuraError('token_exchange_uncertain') from None
                delay = retry_delay(None, attempt)
            if delay > 5 or attempt == 2:
                raise OuraError('retry_later', retry_after=delay)
            time.sleep(delay)
    finally:
        if own:
            client.close()
