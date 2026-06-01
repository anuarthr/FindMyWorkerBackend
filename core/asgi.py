import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from orders.middleware import JWTAuthMiddleware
import orders.routing

django_asgi_app = get_asgi_application()

# Warm the TF-IDF recommendation model in-process so the first search request is
# instant. With the in-memory cache the boot-time `train_recommendation_model`
# command runs in a separate process and its result is lost; training here (in
# the uvicorn worker) makes the model available to request handlers. Best-effort:
# an empty DB or transient error must never block server startup.
try:
    from users.services import RecommendationEngine

    RecommendationEngine().train_model()
except Exception:  # noqa: BLE001 - warm-up is best-effort
    import logging

    logging.getLogger(__name__).warning(
        "Recommendation model warm-up skipped at startup", exc_info=True
    )

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        URLRouter(
            orders.routing.websocket_urlpatterns
        )
    ),
})
