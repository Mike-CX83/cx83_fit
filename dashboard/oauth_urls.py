from django.urls import path
from . import oauth

app_name = 'oauth2_provider'
urlpatterns = [
    path('authorize/', oauth.authorize, name='authorize'),
    path('token/', oauth.token, name='token'),
    path('revoke/', oauth.revoke_token, name='revoke-token'),
]
