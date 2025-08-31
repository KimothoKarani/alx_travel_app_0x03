# alx_travel_app/listings/urls.py
from django.http import JsonResponse
from django.urls import path # Import path
from rest_framework.routers import DefaultRouter
from .views import (UserViewSet, BookingViewSet, PaymentViewSet,
                    ReviewViewSet, MessageViewSet, PropertyViewSet,
                    initiate_chapa_payment, verify_chapa_payment) # Import new views

#Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'properties', PropertyViewSet, basename='properties')
router.register(r'bookings', BookingViewSet, basename='bookings')
router.register(r'payments', PaymentViewSet, basename='payments') # This is your ViewSet for CRUD on payments
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'messages', MessageViewSet, basename='messages')


#The API URLS are now automatically determined by the router
urlpatterns = router.urls

# Add new URL patterns for Chapa integration
urlpatterns += [
    path('api/payments/chapa/initiate/', initiate_chapa_payment, name='chapa_initiate_payment'),
    path('api/payments/chapa/verify/<str:tx_ref>/', verify_chapa_payment, name='chapa_verify_payment'),
    # Add simple placeholder URLs for success/fail pages (you'd implement these with proper templates/views)
    path('payment-success/', lambda request: JsonResponse({'message': 'Payment successful!'}), name='payment_success'),
    path('payment-fail/', lambda request: JsonResponse({'message': 'Payment failed!'}), name='payment_fail'),
    path('payment-status/', lambda request: JsonResponse({'message': 'Payment status check.'}), name='payment_status'),
]