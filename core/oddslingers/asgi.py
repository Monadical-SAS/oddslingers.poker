import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oddslingers.settings")

from django.core.asgi import get_asgi_application

# Initialize Django app registry before any imports that touch models
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from ui.urls import socket_routing  # noqa: E402

# AllowedHostsOriginValidator rejects cross-origin WebSocket handshakes
# (Channels 4 removed the implicit same-origin check that Channels 1 had).
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(socket_routing))
        ),
    }
)
