"""Outbound texts from the app number. Mike's personal phone is never the sender."""
import base64
import hashlib
import hmac
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class SmsError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def configured():
    return bool(
        settings.SMS_ENABLED and settings.SMS_ACCOUNT_SID and settings.SMS_FROM_NUMBER
        and settings.SMS_AUTH_TOKEN_FILE)


def _token():
    from tracking.oura.auth import private_secret
    try:
        return private_secret(settings.SMS_AUTH_TOKEN_FILE)
    except Exception:
        raise SmsError('app_number_missing') from None


def send_text(to, body):
    """Hand one text to the provider. Returns the provider id. Raises SmsError."""
    if not configured():
        raise SmsError('app_number_missing')
    if not isinstance(to, str) or not to.startswith('+') or not isinstance(body, str) or not body:
        raise SmsError('invalid_message')
    url = f'https://api.twilio.com/2010-04-01/Accounts/{settings.SMS_ACCOUNT_SID}/Messages.json'
    payload = urlencode({'To': to, 'From': settings.SMS_FROM_NUMBER, 'Body': body}).encode()
    request = Request(url, data=payload, method='POST')
    basic = base64.b64encode(f'{settings.SMS_ACCOUNT_SID}:{_token()}'.encode()).decode()
    request.add_header('Authorization', f'Basic {basic}')
    request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read(4096)
            status = response.status
    except HTTPError as exc:
        raise SmsError(f'provider_http_{exc.code}') from None
    except (URLError, TimeoutError, OSError):
        raise SmsError('provider_unreachable') from None
    if status not in {200, 201}:
        raise SmsError(f'provider_http_{status}')
    import json
    try:
        provider_id = json.loads(raw.decode('utf-8')).get('sid')
    except (UnicodeError, json.JSONDecodeError, AttributeError):
        raise SmsError('provider_unreadable') from None
    if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 64:
        raise SmsError('provider_unreadable')
    return provider_id


def valid_signature(url, params, header):
    if not configured() or not header or not isinstance(url, str):
        return False
    material = url + ''.join(key + params[key] for key in sorted(params))
    digest = hmac.new(_token().encode(), material.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, header)
