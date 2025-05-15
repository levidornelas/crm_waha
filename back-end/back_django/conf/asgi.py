import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from django.core.asgi import get_asgi_application

import apps.whatsapp.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            apps.whatsapp.routing.websocket_urlpatterns
        )
    ),
})
