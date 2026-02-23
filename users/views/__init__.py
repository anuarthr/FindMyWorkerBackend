"""
Users app views.

Organized into focused modules:
    - auth_views: Authentication (register, login)
    - user_views: User and worker profile management
    - recommendation_views: ML-powered worker recommendations
    - analytics_views: Admin analytics and health monitoring
"""

# Authentication
from .auth_views import (
    RegisterView,
    CustomTokenObtainPairView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

# User Management
from .user_views import (
    ManageUserView,
    ManageWorkerProfileView,
    WorkerAdminViewSet,
)

# ML Recommendations
from .recommendation_views import (
    WorkerRecommendationView,
)

# Analytics & Monitoring
from .analytics_views import (
    RecommendationAnalyticsView,
    RecommendationHealthView,
)

__all__ = [
    # Auth
    'RegisterView',
    'CustomTokenObtainPairView',
    'ChangePasswordView',
    'PasswordResetRequestView',
    'PasswordResetConfirmView',
    # Users
    'ManageUserView',
    'ManageWorkerProfileView',
    'WorkerAdminViewSet',
    # Recommendations
    'WorkerRecommendationView',
    # Analytics
    'RecommendationAnalyticsView',
    'RecommendationHealthView',
]
