import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
from django.core.asgi import get_asgi_application

django_app = get_asgi_application()
# MCP is mounted by build_application only after all OAuth configuration exists.
from dashboard.mcp_server import build_application
from dashboard.request_limits import DjangoRequestLimits
application = build_application(DjangoRequestLimits(django_app))
