"""Accept configured login names for the single private owner account."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class OwnerAliasBackend(ModelBackend):
    """Map an allowed login name to the one owner account after a password check.

    The dashboard stores records on OWNER_USERNAME. Extra names in
    LOGIN_USERNAMES are sign-in labels for that same account.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        submitted = username.strip().casefold()
        aliases = {
            name.casefold()
            for name in settings.LOGIN_USERNAMES
            if name.casefold() != settings.OWNER_USERNAME.casefold()
        }
        if submitted not in aliases:
            return None
        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=settings.OWNER_USERNAME)
        except user_model.DoesNotExist:
            return None
        if owner.check_password(password) and self.user_can_authenticate(owner):
            return owner
        return None
