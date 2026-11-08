"""Owner policy around maintained OAuth Toolkit issuance; no custom OAuth protocol."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from functools import wraps

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from mcp.server.auth.provider import AccessToken as MCPAccessToken, TokenVerifier
from oauthlib.oauth2.rfc6749.errors import InvalidScopeError, CustomOAuth2Error
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import AuthorizationView, TokenView, RevokeTokenView, OAuthServerMetadataView

from dashboard.private_key_jwt import install as install_private_key_jwt, verify as verify_private_key_jwt
from tracking.views import owner_only

install_private_key_jwt()


class OwnerOAuthValidator(OAuth2Validator):
    def client_authentication_required(self, request, *args, **kwargs):
        from dashboard.private_key_jwt import _requirements
        requirements = _requirements(getattr(request, 'client_id', None))
        if requirements and (getattr(request, 'client_assertion', None) or not requirements.get('allow_none')):
            return True
        return super().client_authentication_required(request, *args, **kwargs)

    def authenticate_client(self, request, *args, **kwargs):
        from dashboard.private_key_jwt import _requirements
        if getattr(request, 'client_assertion', None) and _requirements(getattr(request, 'client_id', None)):
            return self._load_application(request.client_id, request) is not None and verify_private_key_jwt(request)
        return super().authenticate_client(request, *args, **kwargs)

    def validate_client_id(self, client_id, request, *args, **kwargs):
        # Even a locally registered client must show the owner's consent form.
        return (super().validate_client_id(client_id, request, *args, **kwargs)
                and not request.client.skip_authorization)

    def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
        return grant_type in {'authorization_code', 'refresh_token'} and super().validate_grant_type(
            client_id, grant_type, client, request, *args, **kwargs)

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        if 'site:write' in scopes and not settings.SITE_EDITS_ENABLED:
            return False
        return ('health:read' in scopes and (settings.HEALTH_OAUTH_WRITES or 'health:write' not in scopes)
                and super().validate_scopes(client_id, scopes, client, request, *args, **kwargs))

    def _check_and_set_request_resource(self, request):
        super()._check_and_set_request_resource(request)
        if request.resource != [settings.HEALTH_OAUTH_RESOURCE]:
            raise CustomOAuth2Error(error='invalid_target', description='The exact dashboard resource is required.', request=request)
        user = request.user
        if not user or not user.is_active or user.get_username() != settings.OWNER_USERNAME:
            raise CustomOAuth2Error(error='access_denied', description='The configured active owner is required.', request=request)
        if not settings.HEALTH_OAUTH_WRITES and 'health:write' in request.scopes:
            raise InvalidScopeError(request=request)


class LocalOwnerTokenVerifier(TokenVerifier):
    """Validate locally issued opaque tokens by checksum; revocation is immediate."""
    def __init__(self, config):
        self.config = config

    def _verify(self, token):
        if not isinstance(token, str) or not 16 <= len(token) <= 4096:
            return None
        record = AccessToken.objects.select_related('user', 'application').filter(
            token_checksum=hashlib.sha256(token.encode()).hexdigest()).first()
        if (record is None or not record.is_valid(['health:read']) or record.user is None
                or not record.user.is_active or record.user.get_username() != settings.OWNER_USERNAME
                or record.application is None or record.resource != [self.config.resource]):
            return None
        return MCPAccessToken(token=token, client_id=record.application.client_id,
            subject=self.config.subject, scopes=record.scope.split(), expires_at=int(record.expires.timestamp()),
            resource=self.config.resource, claims={'iss': self.config.issuer})

    async def verify_token(self, token):
        return await sync_to_async(self._verify, thread_sensitive=True)(token)


def builtin_only(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not settings.HEALTH_OAUTH_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)
    return guarded


@builtin_only
@owner_only
@require_http_methods(['GET', 'POST'])
def authorize(request):
    data = request.GET if request.method=='GET' else request.POST
    resources = data.getlist('resource') if request.method=='GET' else data.get('resource', '').split()
    if resources != [settings.HEALTH_OAUTH_RESOURCE]:
        return JsonResponse({'error': 'invalid_target', 'error_description': 'The exact dashboard resource is required.'}, status=400)
    if data.get('code_challenge_method') != 'S256' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', data.get('code_challenge', '')):
        return JsonResponse({'error': 'invalid_request', 'error_description': 'PKCE S256 is required.'}, status=400)
    if request.method == 'GET':
        request.GET = request.GET.copy()
        request.GET['approval_prompt'] = 'force'
    response = AuthorizationView.as_view(template_name='tracking/oauth_authorize.html')(request)
    context = getattr(response, 'context_data', None) or {}
    # Chrome applies form-action to the callback redirect as well as the local
    # POST. Allow only the exact callback origin already validated by Toolkit,
    # and only on this consent document. All other pages stay self-only.
    if response.status_code == 200 and context.get('application') and not context.get('error'):
        callback = context.get('redirect_uri', '')
        if context['application'].redirect_uri_allowed(callback):
            parsed = urlsplit(callback)
            if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
                response.oauth_callback_origin = parsed.scheme+'://'+parsed.netloc
    # Toolkit 3.4.1 includes iss on successful responses, but its consent-denial
    # redirect omits it. Complete RFC 9207 only after Toolkit validates the client
    # and redirect. Never construct a callback from unvalidated request input.
    if response.status_code == 302 and response.has_header('Location'):
        target = urlsplit(response['Location'])
        fields = parse_qsl(target.query, keep_blank_values=True)
        if any(key in {'code', 'error'} for key, value in fields):
            fields = [(key, value) for key, value in fields if key != 'iss']
            fields.append(('iss', settings.HEALTH_OAUTH_ORIGIN))
            response['Location'] = urlunsplit((target.scheme, target.netloc, target.path, urlencode(fields), target.fragment))
    return response


# OAuth token/revocation requests authenticate via the protocol, not browser
# cookies. Toolkit supplies PKCE, client validation, rotation and revocation.
token = csrf_exempt(builtin_only(TokenView.as_view()))
revoke_token = csrf_exempt(builtin_only(RevokeTokenView.as_view()))
metadata = builtin_only(OAuthServerMetadataView.as_view())


@owner_only
@require_http_methods(['GET'])
def connections(request):
    tokens = AccessToken.objects.filter(user=request.user).select_related('application').order_by('-created')[:100]
    return render(request, 'tracking/connections.html', {'enabled': settings.HEALTH_OAUTH_ENABLED,
        'tokens': tokens, 'resource': settings.HEALTH_OAUTH_RESOURCE if settings.HEALTH_OAUTH_ENABLED else '',
        'writes': settings.HEALTH_OAUTH_WRITES})


@builtin_only
@owner_only
@require_http_methods(['POST'])
def disconnect(request, application_id):
    if request.POST.get('confirm_revoke') != 'yes':
        return HttpResponseBadRequest('Confirm revocation first.')
    with transaction.atomic():
        application = get_object_or_404(Application, pk=application_id,
            pk__in=AccessToken.objects.filter(user=request.user).values('application_id'))
        # Remove refresh capability as well as current bearer tokens and pending
        # authorization codes. Other owners and applications remain untouched.
        RefreshToken.objects.filter(user=request.user, application=application).delete()
        AccessToken.objects.filter(user=request.user, application=application).delete()
        Grant.objects.filter(user=request.user, application=application).delete()
    return redirect('connections')
