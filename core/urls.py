from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from users.views import RegisterView, ManageWorkerProfileView, WorkerAdminViewSet, CustomTokenObtainPairView
from users.views_public import WorkerDiscoveryViewSet
from orders.views import list_reviews

router = DefaultRouter()
router.register(r'api/workers', WorkerDiscoveryViewSet, basename='worker-discovery')
admin_router = DefaultRouter()
admin_router.register(r'api/admin/workers', WorkerAdminViewSet, basename='worker-admin')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('users.urls')),
    path('api/workers/me/', ManageWorkerProfileView.as_view(), name='worker_profile'),
    path('api/orders/', include('orders.urls')),
    path('api/reviews/', list_reviews, name='list-reviews'),
    path('', include(router.urls)),
    path('', include(admin_router.urls)),
]

# Serve media files in development (local storage only)
if settings.DEBUG and not settings.USE_S3:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
