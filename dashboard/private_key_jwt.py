"""Accept ChatGPT's private_key_jwt client metadata and verify its assertion.

Django OAuth Toolkit 3.4.1 registers CIMD clients only when their metadata says
token_endpoint_auth_method is none. ChatGPT's published document uses
private_key_jwt and publishes the matching RSA key at jwks_uri. This module
lets that document through registration, then requires a signed client
assertion at the token endpoint. Public clients and client secrets stay as
they were.
"""
import base64
import hashlib
import json
import time
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from jwcrypto import jwk, jwt
from jwcrypto.common import JWException
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher, _build_application_kwargs
from oauth2_provider.models import get_application_model

ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
_INSTALLED = False
_ORIGINAL_BUILD = _build_application_kwargs


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    import oauth2_provider.cimd as cimd
    cimd._build_application_kwargs = _accept_private_key_jwt
    _INSTALLED = True


def _accept_private_key_jwt(metadata):
    if metadata.get('token_endpoint_auth_method') != 'private_key_jwt':
        return _ORIGINAL_BUILD(metadata)
    _require_metadata(metadata)
    return _ORIGINAL_BUILD({**metadata, 'token_endpoint_auth_method': 'none'})


def _require_metadata(metadata):
    if metadata.get('token_endpoint_auth_signing_alg') != 'RS256':
        raise CIMDError('private_key_jwt requires RS256')
    methods = metadata.get('token_endpoint_auth_methods_supported')
    if methods is not None:
        if not isinstance(methods, list) or not all(isinstance(item, str) for item in methods):
            raise CIMDError('token_endpoint_auth_methods_supported must be an array of strings')
        if 'private_key_jwt' not in methods or any(item.startswith('client_secret') for item in methods):
            raise CIMDError('private_key_jwt metadata cannot advertise a client secret')
    jwks_uri = metadata.get('jwks_uri')
    client_id = metadata.get('client_id')
    if not isinstance(jwks_uri, str) or not isinstance(client_id, str):
        raise CIMDError('private_key_jwt requires a jwks_uri on the client host')
    key_url = urlparse(jwks_uri)
    client_url = urlparse(client_id)
    if (key_url.scheme != 'https' or not key_url.hostname or not key_url.path
            or key_url.username or key_url.password or key_url.query or key_url.fragment
            or key_url.hostname.lower() != (client_url.hostname or '').lower()
            or any(segment in {'.', '..'} for segment in key_url.path.split('/'))):
        raise CIMDError('jwks_uri must be https on the same host as the client_id')


def _requirements(client_id):
    Application = get_application_model()
    application = Application.objects.filter(client_id=client_id).first()
    if application is None or application.registration_source != Application.RegistrationSource.CIMD:
        return None
    cache_key = 'private-key-jwt:' + hashlib.sha256(client_id.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached == 'public':
        return None
    if isinstance(cached, dict):
        return cached
    try:
        metadata, _max_age = SafeMetadataFetcher().fetch(client_id)
    except CIMDError:
        return None
    if metadata.get('client_id') != client_id or metadata.get('token_endpoint_auth_method') != 'private_key_jwt':
        cache.set(cache_key, 'public', 60)
        return None
    try:
        _require_metadata(metadata)
    except CIMDError:
        return None
    methods = metadata.get('token_endpoint_auth_methods_supported') or []
    value = {'jwks_uri': metadata['jwks_uri'], 'allow_none': 'none' in methods}
    cache.set(cache_key, value, 60)
    return value


def requires_assertion(client_id):
    return bool(client_id) and _requirements(client_id) is not None


def _token_audiences():
    origin = settings.HEALTH_OAUTH_ORIGIN.rstrip('/')
    return {origin + '/oauth/token', origin + '/oauth/token/'}


def _header(assertion):
    try:
        segment = assertion.split('.', 2)[0]
        padded = segment + '=' * (-len(segment) % 4)
        header = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError, IndexError):
        return None
    if not isinstance(header, dict) or header.get('alg') != 'RS256' or 'jwk' in header or 'x5c' in header:
        return None
    if header.get('typ') not in {None, 'JWT'}:
        return None
    return header


def _audience_matches(audience):
    allowed = _token_audiences()
    if isinstance(audience, str):
        return audience in allowed
    return isinstance(audience, list) and any(item in allowed for item in audience)


def verify(request):
    requirements = _requirements(getattr(request, 'client_id', None))
    assertion = getattr(request, 'client_assertion', None)
    if (requirements is None or getattr(request, 'client_assertion_type', None) != ASSERTION_TYPE
            or not isinstance(assertion, str) or assertion.count('.') != 2 or _header(assertion) is None):
        return False
    try:
        document, _max_age = SafeMetadataFetcher().fetch(requirements['jwks_uri'])
        keys = document.get('keys') if isinstance(document, dict) else None
        if not isinstance(keys, list) or not keys:
            return False
        usable = [key for key in keys if isinstance(key, dict) and key.get('kty') == 'RSA'
                  and key.get('alg') in {None, 'RS256'} and 'd' not in key]
        if not usable:
            return False
        checked = jwt.JWT(jwt=assertion, key=jwk.JWKSet.from_json(json.dumps({'keys': usable})),
                           algs=['RS256'], expected_type='JWS')
        claims = json.loads(checked.claims)
    except (CIMDError, JWException, ValueError, json.JSONDecodeError, TypeError):
        return False
    now = time.time()
    issued = claims.get('iat')
    expires = claims.get('exp')
    identifier = claims.get('jti')
    if (claims.get('iss') != request.client_id or claims.get('sub') != request.client_id
            or not _audience_matches(claims.get('aud'))
            or not isinstance(issued, (int, float)) or not isinstance(expires, (int, float))
            or issued > now + 60 or expires <= now - 60 or expires > issued + 600
            or not isinstance(identifier, str) or not 8 <= len(identifier) <= 128):
        return False
    if 'nbf' in claims and (not isinstance(claims['nbf'], (int, float)) or claims['nbf'] > now + 60):
        return False
    replay_key = 'private-key-jwt-jti:' + hashlib.sha256(
        (request.client_id + '\0' + identifier).encode()).hexdigest()
    if not cache.add(replay_key, 1, timeout=max(1, min(600, int(expires - now) + 60))):
        return False
    return request.client is not None
