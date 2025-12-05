from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from users.views import RegisterView, ManageWorkerProfileView, WorkerAdminViewSet 
from users.views_public import WorkerDiscoveryViewSet

router = DefaultRouter()
router.register(r'api/workers', WorkerDiscoveryViewSet, basename='worker-discovery')
admin_router = DefaultRouter()
# /api/admin/workers/pending/ y /api/admin/workers/{id}/approve/
admin_router.register(r'api/admin/workers', WorkerAdminViewSet, basename='worker-admin')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('users.urls')),
    path('api/workers/me/', ManageWorkerProfileView.as_view(), name='worker_profile'),
    path('', include(router.urls)),
    path('', include(admin_router.urls)),
]
