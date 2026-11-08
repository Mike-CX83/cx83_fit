def no_ip(request):
    return None


class PrivateResponses:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Cache-Control'] = 'private, no-store'
        response['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        callback = getattr(response, 'oauth_callback_origin', None)
        if callback:
            response['Content-Security-Policy'] += ' ' + callback
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
