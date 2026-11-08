"""oauthlib authorization code + PKCE; encrypted credentials and persistent leases."""
from datetime import timedelta
import hashlib
import math
import os
from pathlib import Path
import secrets
import stat
from urllib.parse import urlsplit
import uuid

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from oauthlib.oauth2 import WebApplicationClient, OAuth2Error

from tracking.models import OuraAuthorization, OuraConnection
from tracking.services import _owner
from .catalog import AUTHORIZE_URL, TOKEN_URL, CALLBACK_PATH, SCOPES, API_BASE
from .transport import OuraError, request, encode, decode


FLOW_COOKIE = 'oura_flow'


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def private_secret(filename):
    try:
        path = Path(filename)
        if path.resolve().is_relative_to(settings.PRIVATE_ROOT.resolve()):
            raise OuraError('secret_must_be_outside_data')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise OuraError('secret_permissions')
            data = handle.read(4097)
            if not data or len(data) > 4096:
                raise OuraError('secret_invalid')
            return data.strip().decode('ascii')
    except (OSError, ValueError, UnicodeError):
        raise OuraError('secret_unavailable') from None


def configured():
    return bool(settings.OURA_ENABLED)


def configuration():
    if not configured():
        raise OuraError('not_configured')
    uri = settings.OURA_REDIRECT_URI
    parts = urlsplit(uri)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.path != CALLBACK_PATH or parts.query or parts.fragment
            or parts.hostname not in settings.ALLOWED_HOSTS):
        raise OuraError('invalid_redirect_configuration')
    if not settings.OURA_CLIENT_ID:
        raise OuraError('not_configured')
    return settings.OURA_CLIENT_ID, uri


def cipher():
    try:
        return Fernet(private_secret(settings.OURA_TOKEN_KEY_FILE).encode('ascii'))
    except (ValueError, TypeError):
        raise OuraError('key_invalid') from None


def seal(value):
    return cipher().encrypt(encode(value).encode('utf-8')).decode('ascii')


def unseal(value):
    try:
        return decode(cipher().decrypt(value.encode('ascii')).decode('utf-8'))
    except (InvalidToken, UnicodeError, ValueError):
        raise OuraError('credential_unavailable') from None


def begin(owner):
    _owner(owner)
    client_id, uri = configuration()
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    client = WebApplicationClient(client_id)
    challenge = client.create_code_challenge(verifier, 'S256')
    payload = seal({'state': state, 'verifier': verifier, 'redirect_uri': uri, 'client_id': client_id})
    # One pending browser authorization per owner; expired flows contain no reusable secrets.
    with transaction.atomic():
        OuraAuthorization.objects.filter(owner=owner).delete()
        OuraAuthorization.objects.create(state_hash=digest(state), owner=owner,
            nonce_hash=digest(nonce), secret_ciphertext=payload,
            expires_at=timezone.now()+timedelta(minutes=10))
    return client.prepare_request_uri(AUTHORIZE_URL, redirect_uri=uri, scope=SCOPES,
        state=state, code_challenge=challenge, code_challenge_method='S256'), nonce


def token_response(body):
    client_id, _ = configuration()
    data, raw = request('POST', TOKEN_URL, body=body,
                       credentials=(client_id, private_secret(settings.OURA_CLIENT_SECRET_FILE)))
    try:
        parsed = WebApplicationClient(client_id).parse_request_body_response(raw)
        if (not isinstance(parsed.get('access_token'), str) or not parsed['access_token']
                or not isinstance(parsed.get('refresh_token'), str) or not parsed['refresh_token']
                or str(parsed.get('token_type', '')).lower() != 'bearer'):
            raise ValueError
        if isinstance(data.get('expires_in'), bool) or any(len(parsed[k]) > 8192 for k in ('access_token', 'refresh_token')):
            raise ValueError
        seconds = float(parsed['expires_in'])
        if not math.isfinite(seconds) or not 0 < seconds <= 366*86400:
            raise ValueError
        scopes = parsed.get('scope')
        if isinstance(scopes, str):
            scopes = scopes.split()
        if scopes is not None and (not isinstance(scopes, list) or not all(isinstance(x, str) for x in scopes)):
            raise ValueError
        tokens = {'access_token': parsed['access_token'], 'refresh_token': parsed['refresh_token']}
        return seal(tokens), timezone.now()+timedelta(seconds=seconds), scopes, tokens
    except (OAuth2Error, ValueError, TypeError, KeyError, OverflowError):
        raise OuraError('invalid_token_response') from None


def finish(query, nonce):
    client_id, uri = configuration()
    # QueryDict permits duplicate keys. Reject ambiguity before any provider exchange.
    if any(len(query.getlist(k)) != 1 for k in query) or not nonce:
        raise OuraError('invalid_authorization_state')
    state = query.get('state', '')
    if not 40 <= len(state) <= 256 or len(nonce) > 256:
        raise OuraError('invalid_authorization_state')
    with transaction.atomic():
        flow = OuraAuthorization.objects.select_related('owner').filter(state_hash=digest(state)).first()
        if (not flow or flow.used_at or flow.expires_at <= timezone.now()
                or not secrets.compare_digest(flow.nonce_hash, digest(nonce))):
            raise OuraError('invalid_authorization_state')
        _owner(flow.owner)
        saved = unseal(flow.secret_ciphertext)
        if saved['redirect_uri'] != uri or saved['client_id'] != client_id:
            raise OuraError('authorization_configuration_changed')
        flow.used_at, flow.secret_ciphertext = timezone.now(), ''
        flow.save(update_fields=['used_at', 'secret_ciphertext'])
    # The committed one time claim precedes external calls, including failed/cancelled exchanges.
    client = WebApplicationClient(client_id)
    try:
        # Scope in callbacks is deprecated; never trust it as the granted scope list.
        clean = query.copy()
        clean.pop('scope', None)
        code = client.parse_request_uri_response(uri+'?'+clean.urlencode(), state=saved['state'])['code']
    except (OAuth2Error, ValueError, KeyError):
        raise OuraError('authorization_declined_or_invalid') from None
    body = client.prepare_request_body(code=code, redirect_uri=uri,
        code_verifier=saved['verifier'], include_client_id=False)
    encrypted, expiry, scopes, tokens = token_response(body)
    account_id = None
    try:
        profile, _ = request('GET', API_BASE+'personal_info', token=tokens['access_token'])
        if not isinstance(profile.get('id'), str) or not profile['id']:
            raise OuraError('invalid_response')
        account_id = profile['id']
    except OuraError as error:
        # Optional personal scope may be declined. Never merge an unidentified account.
        if error.code not in {'permission_or_membership', 'unauthorized'}:
            raise
    key = 'id:'+digest(account_id) if account_id else 'unidentified:'+uuid.uuid4().hex
    with transaction.atomic():
        connection, _ = OuraConnection.objects.get_or_create(owner=flow.owner, account_key=key,
                                                            synthetic=False)
        connection.source_account_id = account_id
        connection.generation = uuid.uuid4()
        connection.token_ciphertext, connection.expires_at, connection.scopes = encrypted, expiry, scopes
        connection.state = 'authorized'
        connection.refresh_lease = connection.refresh_until = None
        connection.sync_lease = connection.sync_until = None
        connection.save()
    return connection


def access_token(owner, connection_id, rejected_token=None):
    _owner(owner)
    configuration()
    expired_lease = False
    with transaction.atomic():
        row = OuraConnection.objects.get(owner=owner, pk=connection_id)
        if row.state == 'refreshing':
            if row.refresh_until and row.refresh_until > timezone.now():
                raise OuraError('refresh_busy')
            # A crashed worker may have spent the single use refresh token. Never replay it.
            row.state, row.token_ciphertext = 'reauthorize', ''
            row.save(update_fields=['state', 'token_ciphertext'])
            expired_lease = True
        elif row.state not in {'authorized', 'connected'}:
            raise OuraError('reauthorize')
        if not expired_lease:
            tokens = unseal(row.token_ciphertext)
            force = rejected_token is not None and secrets.compare_digest(rejected_token, tokens['access_token'])
            if not force and row.expires_at and row.expires_at > timezone.now()+timedelta(seconds=60):
                return tokens['access_token']
            lease = uuid.uuid4()
            row.state, row.refresh_lease = 'refreshing', lease
            row.refresh_until = timezone.now()+timedelta(seconds=90)
            row.save(update_fields=['state', 'refresh_lease', 'refresh_until'])
    if expired_lease:
        raise OuraError('reauthorize')
    owned = OuraConnection.objects.filter(pk=row.pk, generation=row.generation,
                                         refresh_lease=lease, state='refreshing')
    try:
        body = WebApplicationClient(settings.OURA_CLIENT_ID).prepare_refresh_body(
            refresh_token=tokens['refresh_token'])
        encrypted, expiry, scopes, new = token_response(body)
        if not owned.update(token_ciphertext=encrypted, expires_at=expiry,
                            scopes=scopes if scopes is not None else row.scopes,
                            state='authorized', refresh_lease=None, refresh_until=None):
            raise OuraError('connection_changed')
        return new['access_token']
    except Exception:
        owned.update(state='reauthorize', token_ciphertext='', refresh_lease=None, refresh_until=None)
        raise OuraError('reauthorize') from None


def disconnect(owner, connection_id):
    _owner(owner)
    OuraConnection.objects.filter(owner=owner, pk=connection_id).update(
        state='disconnected', token_ciphertext='', expires_at=None, generation=uuid.uuid4(),
        refresh_lease=None, refresh_until=None, sync_lease=None, sync_until=None)
    OuraAuthorization.objects.filter(owner=owner).delete()
