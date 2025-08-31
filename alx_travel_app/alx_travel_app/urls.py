# project_name/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static file helper

# Import JWT views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# --- Import drf-spectacular views ---
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    # Django admin panel
    path('admin/', admin.site.urls),

    # --- Your main API endpoints ---
    path('api/', include('listings.urls')),

    # --- JWT Authentication endpoints ---
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # --- drf-spectacular schema and documentation URLs ---
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# ONLY SERVE STATIC FILES THIS WAY IN DEVELOPMENT (DEBUG=TRUE)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # If you also have MEDIA_ROOT for user-uploaded files, add this too:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)