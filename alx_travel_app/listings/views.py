# alx_travel_app/listings/views.py
from drf_spectacular.types import OpenApiTypes
from rest_framework import viewsets, filters, status, permissions
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny, IsAdminUser
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, inline_serializer, OpenApiParameter
from rest_framework import serializers # Needed for inline_serializer

# New imports for Chapa and Celery
import requests
import json
import uuid # For generating unique transaction references
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt # Use with caution in production, or use DRF's APIView
from django.shortcuts import get_object_or_404
from .tasks import send_booking_confirmation_email, send_payment_confirmation_email


from .serializers import (
    NestedUserSerializer,
    PropertySerializer,
    NestedPropertySerializer,
    BookingSerializer,
    MessageSerializer,
    ReviewSerializer,
    PaymentSerializer
)
from .models import User, Property, Booking, Payment, Review, Message


# --- Chapa API Endpoints (Constants) ---
CHAPA_INITIATE_URL = "https://api.chapa.co/v1/initialize"
CHAPA_VERIFY_URL = "https://api.chapa.co/v1/verify/" # Note: takes a transaction_id after the slash



# -------------------------
# CUSTOM PERMISSIONS
# -------------------------
class IsPropertyHost(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.host == request.user


class IsBookingOwner(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.user == request.user


class IsReviewOwner(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.user == request.user


class IsMessageSender(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.sender == request.user


# -------------------------
# VIEWS
# -------------------------

@extend_schema(
    tags=["Users"],
    summary="Retrieve user information",
    description="Provides read-only access to user profiles. Intended for public profile data retrieval.",
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = NestedUserSerializer
    permission_classes = [AllowAny]


@extend_schema(
    tags=["Properties"],
    summary="Manage property listings",
    description="View, create, update, and delete properties. Only property owners can edit or delete their listings.",
    responses={
        200: OpenApiResponse(
            response=NestedPropertySerializer,
            description="List of properties retrieved successfully.",
            examples=[
                OpenApiExample(
                    "Property example",
                    value={
                        "property_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                        "name": "Cozy Beachfront Villa",
                        "description": "Stunning views, private beach access.",
                        "location": "Malibu, CA",
                        "price_per_night": "500.00",
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z",
                        "host": {
                            "user_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "email": "jane.doe@example.com",
                            "phone_number": "555-123-4567",
                            "role": "host"
                        }
                    },
                    media_type="application/json",
                )
            ],
        ),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        403: OpenApiResponse(description="Permission denied."),
        404: OpenApiResponse(description="Property not found."),
    }
)
class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all()
    serializer_class = NestedPropertySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)

    def get_queryset(self):
        return super().get_queryset()

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsPropertyHost]
        elif self.action == 'create':
            self.permission_classes = [IsAuthenticated]
        else:
            self.permission_classes = [AllowAny]
        return [permission() for permission in self.permission_classes]


@extend_schema(
    tags=["Bookings"],
    summary="Manage bookings",
    description="Authenticated users can create and view their bookings. Hosts can view bookings for their properties. Only booking creators can modify or cancel bookings.",
    responses={
        200: OpenApiResponse(
            response=BookingSerializer,
            description="List of bookings retrieved successfully.",
            examples=[
                OpenApiExample(
                    "Booking example",
                    value={
                        "booking_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                        "property": { # Full nested property object
                            "property_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                            "name": "Cozy Beachfront Villa",
                            "location": "Malibu, CA",
                            "price_per_night": "500.00"
                        },
                        "user": { # Full nested user object
                            "user_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "email": "jane.doe@example.com"
                        },
                        "start_date": "2025-08-01",
                        "end_date": "2025-08-05",
                        "total_price": "800.00",
                        "status": "confirmed",
                        "created_at": "2025-07-20T10:00:00Z"
                    },
                    media_type="application/json",
                )
            ],
        )
    }
)
class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """
        Assigns the authenticated user to the booking
        and calculates total_price automatically.
        """
        property_obj = serializer.validated_data["property"]
        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]

        # Calculate number of nights
        nights = (end_date - start_date).days
        total_price = nights * property_obj.price_per_night

        # Save booking with calculated price + user from request
        booking = serializer.save(user=self.request.user, total_price=total_price)

        # Trigger Celery task
        send_booking_confirmation_email.delay(str(booking.booking_id), booking.user.email)
        print(f"DEBUG: Booking confirmation email task for booking {booking.booking_id} triggered via Celery.")

    def get_queryset(self):
        """
        Guests see their bookings. Hosts see bookings for their properties.
        """
        user = self.request.user
        if user.is_authenticated:
            return Booking.objects.filter(Q(user=user) | Q(property__host=user)).distinct()
        return Booking.objects.none()

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsBookingOwner]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]


@extend_schema(
    tags=["Payments"],
    summary="Handle payments for bookings",
    description="View and create payments related to bookings. Only admins can update or delete payments.",
    responses={
        200: OpenApiResponse(
            response=PaymentSerializer,
            description="List of payments retrieved successfully.",
            examples=[
                OpenApiExample(
                    "Payment example",
                    value={
                        "payment_id": "e6f7g8h9-i0j1-2345-6789-0abcdef12345",
                        "booking": { # Nested booking object
                            "booking_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                            "start_date": "2025-08-01",
                            "end_date": "2025-08-05",
                            "total_price": "800.00"
                        },
                        "amount": "400.00",
                        "payment_date": "2025-08-01T10:00:00Z",
                        "payment_method": "chapa",
                        "chapa_transaction_id": "chapa-tx-12345",
                        "status": "COMPLETED",
                        "chapa_status_text": "Payment successful"
                    },
                    media_type="application/json",
                )
            ],
        )
    }
)
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Payment.objects.filter(Q(booking__user=user) | Q(booking__property__host=user)).distinct()
        return Payment.objects.none()

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]


@extend_schema(
    tags=["Reviews"],
    summary="Manage property and booking reviews",
    description="Anyone can view reviews. Authenticated users can create reviews. Only review authors can edit or delete them.",
    responses={
        200: OpenApiResponse(
            response=ReviewSerializer,
            description="List of reviews retrieved successfully.",
            examples=[
                OpenApiExample(
                    "Review example",
                    value={
                        "review_id": "f7g8h9i0-j1k2-3456-7890-1abcdef23456",
                        "property": {
                            "property_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                            "name": "Cozy Beachfront Villa",
                            "location": "Malibu, CA",
                            "price_per_night": "500.00"
                        },
                        "user": {
                            "user_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "email": "jane.doe@example.com"
                        },
                        "rating": 5,
                        "comment": "Absolutely loved this place! Clean, spacious, and amazing host.",
                        "created_at": "2025-07-15T12:00:00Z"
                    },
                    media_type="application/json",
                )
            ],
        )
    }
)
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsReviewOwner]
        else:
            self.permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in self.permission_classes]


@extend_schema(
    tags=["Messages"],
    summary="Send and receive user messages",
    description="Authenticated users can send messages to each other. A user can only view messages they sent or received. Only senders can edit or delete messages. Supports threaded conversations.",
    responses={
        200: OpenApiResponse(
            response=MessageSerializer,
            description="List of messages retrieved successfully.",
            examples=[
                OpenApiExample(
                    "Top-level message example",
                    value={
                        "message_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                        "sender": {
                            "user_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "email": "jane.doe@example.com"
                        },
                        "receiver": {
                            "user_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef01",
                            "first_name": "John",
                            "last_name": "Smith",
                            "email": "john.smith@example.com"
                        },
                        "message_body": "Hi, is the property available for these dates?",
                        "sent_at": "2025-08-01T14:30:00Z",
                        "parent_message": None # No parent message for top-level
                    },
                    media_type="application/json",
                ),
                OpenApiExample(
                    "Reply message example",
                    value={
                        "message_id": "f1e2d3c4-b5a6-9876-5432-10fedcba9876",
                        "sender": {
                            "user_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef01",
                            "first_name": "John",
                            "last_name": "Smith",
                            "email": "john.smith@example.2.com"
                        },
                        "receiver": None, # Recipient might be null for a pure reply in a thread
                        "message_body": "Yes, it is! What dates were you thinking?",
                        "sent_at": "2025-08-01T14:35:00Z",
                        "parent_message": "a1b2c3d4-e5f6-7890-1234-567890abcdef", # ID of the parent message
                    },
                    media_type="application/json",
                )
            ],
        )
    }
)
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Message.objects.filter(Q(sender=user) | Q(recipient=user)).distinct()
        return Message.objects.none()

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsMessageSender]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]


# --- Chapa Payment Integration Views ---

@extend_schema(
    tags=["Chapa Payments"],
    summary="Initiate a Chapa payment for a booking",
    description="This endpoint starts the payment process with Chapa. It creates a pending payment record and returns Chapa's checkout URL, to which the user should be redirected.",
    request=inline_serializer(
        name='InitiateChapaPaymentRequest',
        fields={
            'booking_id': serializers.UUIDField(help_text="UUID of the booking to pay for."),
            'amount': serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Amount to pay for the booking.")
        }
    ),
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name='InitiateChapaPaymentSuccessResponse',
                fields={
                    'status': serializers.CharField(),
                    'checkout_url': serializers.URLField(),
                    'tx_ref': serializers.CharField(),
                }
            ),
            description="Payment initiated successfully. Redirect user to `checkout_url`."
        ),
        400: OpenApiResponse(description="Invalid request data or booking not found."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        500: OpenApiResponse(description="Internal server error or Chapa API connectivity issue.")
    }
)
@csrf_exempt # In production, use DRF's APIView or appropriate CSRF protection.
def initiate_chapa_payment(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required.'}, status=401)
        
        try:
            data = json.loads(request.body)
            booking_id = data.get('booking_id')
            amount = data.get('amount')

            if not booking_id or not amount:
                return JsonResponse({'error': 'Booking ID and amount are required.'}, status=400)
            
            # Retrieve the booking to get user details and validate amount
            try:
                booking = Booking.objects.get(booking_id=booking_id, user=request.user)
                # You might want to enforce that amount == booking.total_price here
                if float(amount) != float(booking.total_price):
                    # Consider if partial payments are allowed or if this is a strict mismatch
                    return JsonResponse({'error': f'Amount {amount} does not match booking total price {booking.total_price}.'}, status=400)

            except Booking.DoesNotExist:
                return JsonResponse({'error': 'Booking not found or you do not own this booking.'}, status=404)

            # Generate a unique transaction reference for Chapa.
            # It's crucial this is unique for each payment attempt and can be mapped back to your system.
            # Using UUID for high uniqueness.
            tx_ref = f"{booking.booking_id.hex}-{uuid.uuid4().hex}"

            # Create a pending payment record BEFORE calling Chapa
            # This links our internal record to the upcoming Chapa transaction
            # and helps track failed initiations.
            payment = Payment.objects.create(
                booking=booking,
                amount=amount,
                payment_method=Payment.PaymentMethodChoices.CHAPA, # Set as Chapa
                chapa_transaction_id=tx_ref, # Use our tx_ref as Chapa's ID initially, will be updated later
                status=Payment.ChapaPaymentStatusChoices.PENDING,
                chapa_status_text='Initiation pending'
            )

            headers = {
                "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "amount": str(amount), # Chapa expects amount as string
                "currency": "ETB", # Or dynamic if you support other currencies
                "email": booking.user.email,
                "first_name": booking.user.first_name,
                "last_name": booking.user.last_name,
                "tx_ref": tx_ref, # Your unique transaction reference
                "callback_url": request.build_absolute_uri(f'/api/payments/chapa/verify/{tx_ref}/'),
                "return_url": request.build_absolute_uri('/payment-status/'), # A generic landing page after Chapa redirect
                "customization": {
                    "title": "Travel Booking Payment",
                    "description": f"Payment for booking {booking.booking_id}"
                }
            }
            
            print(f"DEBUG: Initiating Chapa payment for tx_ref: {tx_ref} with payload: {payload}")
            chapa_response = requests.post(CHAPA_INITIATE_URL, headers=headers, json=payload)
            chapa_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            response_data = chapa_response.json()
            print(f"DEBUG: Chapa initiation response: {response_data}")

            if response_data.get('status') == 'success':
                checkout_url = response_data['data']['checkout_url']
                # Chapa's `transaction_id` might be different from `tx_ref` but `tx_ref` is what we use to verify
                # payment.chapa_transaction_id = response_data['data'].get('transaction_id', tx_ref) # Update with Chapa's official transaction_id if provided
                payment.chapa_status_text = response_data.get('message', 'Payment initiation successful, awaiting completion.')
                payment.save()

                return JsonResponse({'status': 'success', 'checkout_url': checkout_url, 'tx_ref': tx_ref})
            else:
                payment.status = Payment.ChapaPaymentStatusChoices.FAILED
                payment.chapa_status_text = response_data.get('message', 'Failed to initiate payment with Chapa.')
                payment.save()
                return JsonResponse({'status': 'error', 'message': payment.chapa_status_text}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body.'}, status=400)
        except requests.exceptions.RequestException as e:
            # Handle network errors or API call failures
            print(f"ERROR: Chapa API request failed during initiation: {e}")
            # Mark payment as failed due to API issue
            if 'payment' in locals() and payment.status == Payment.ChapaPaymentStatusChoices.PENDING:
                payment.status = Payment.ChapaPaymentStatusChoices.FAILED
                payment.chapa_status_text = f"API Request Error: {e}"
                payment.save()
            return JsonResponse({'status': 'error', 'message': 'Could not connect to payment gateway or API error.'}, status=500)
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during payment initiation: {e}")
            if 'payment' in locals() and payment.status == Payment.ChapaPaymentStatusChoices.PENDING:
                payment.status = Payment.ChapaPaymentStatusChoices.FAILED
                payment.chapa_status_text = f"Internal Error: {e}"
                payment.save()
            return JsonResponse({'status': 'error', 'message': f'An internal error occurred: {e}'}, status=500)
    return JsonResponse({'error': 'Invalid request method. Only POST is allowed.'}, status=405)


@extend_schema(
    tags=["Chapa Payments"],
    summary="Verify a Chapa payment status via callback",
    description="This endpoint is called by Chapa (or by your frontend after redirection) to verify the final status of a payment. It queries Chapa's API and updates the payment record accordingly. Triggers confirmation email on success.",
    parameters=[
        OpenApiParameter(
            name='tx_ref',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='The transaction reference ID generated by your system during payment initiation.'
        )
    ],
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name='VerifyChapaPaymentSuccessResponse',
                fields={
                    'status': serializers.CharField(),
                    'message': serializers.CharField(),
                    'payment_status': serializers.CharField(), # e.g., 'COMPLETED'
                }
            ),
            description="Payment verification successful. Status updated."
        ),
        302: OpenApiResponse(description="Redirects to a success or failure page after processing."), # For the redirect
        404: OpenApiResponse(description="Payment record not found."),
        500: OpenApiResponse(description="Internal server error or Chapa API connectivity issue.")
    }
)
@csrf_exempt # In production, use DRF's APIView or appropriate CSRF protection.
def verify_chapa_payment(request, tx_ref):
    # This endpoint is accessed when Chapa redirects the user back to your site.
    # It should ideally be idempotent: multiple calls for the same tx_ref should not cause issues.
    
    try:
        payment = get_object_or_404(Payment, chapa_transaction_id=tx_ref)

        # IMPORTANT: Avoid re-processing if already completed or failed
        if payment.status in [Payment.ChapaPaymentStatusChoices.COMPLETED, Payment.ChapaPaymentStatusChoices.FAILED]:
            print(f"DEBUG: Payment {tx_ref} already processed with status: {payment.status}. Skipping re-verification.")
            # Redirect to a status page that shows the current status
            return HttpResponseRedirect(f'/payment-status/?tx_ref={tx_ref}&status={payment.status.lower()}')

        headers = {
            "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Verifying Chapa payment for tx_ref: {tx_ref}")
        chapa_response = requests.get(f"{CHAPA_VERIFY_URL}{tx_ref}", headers=headers)
        chapa_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        response_data = chapa_response.json()
        print(f"DEBUG: Chapa verification response: {response_data}")

        # Chapa's verification response structure:
        # { "status": "success", "message": "Payment details", "data": { ... payment info ... "status": "success", ... } }
        if response_data.get('status') == 'success' and response_data['data'].get('status') == 'success':
            payment.status = Payment.ChapaPaymentStatusChoices.COMPLETED
            payment.chapa_status_text = response_data['data'].get('status', 'Payment completed successfully.')
            payment.save()

            # Update booking status if payment is successful
            if payment.booking.status != Booking.BookingStatusChoices.CONFIRMED:
                payment.booking.status = Booking.BookingStatusChoices.CONFIRMED
                payment.booking.save()
                print(f"DEBUG: Booking {payment.booking.booking_id} status updated to CONFIRMED.")

            # Trigger email sending in background using Celery
            # Get the actual email from the associated booking's user
            recipient_email = payment.booking.user.email
            send_payment_confirmation_email.delay(str(payment.payment_id), recipient_email, payment.amount, str(payment.booking.booking_id))
            print(f"DEBUG: Payment confirmation email task for payment {payment.payment_id} triggered via Celery.")

            # Redirect user to a success page
            return HttpResponseRedirect('/payment-success/')
        else:
            # Payment failed or is not successful from Chapa's perspective
            payment.status = Payment.ChapaPaymentStatusChoices.FAILED
            # Try to get a more specific message from 'data' first, then from top-level 'message'
            payment.chapa_status_text = response_data['data'].get('message', response_data.get('message', 'Payment verification failed.'))
            payment.save()
            print(f"DEBUG: Payment {tx_ref} failed. Status: {payment.chapa_status_text}")
            # Redirect user to a failure page, possibly with error details
            return HttpResponseRedirect(f'/payment-fail/?tx_ref={tx_ref}&status={payment.chapa_status_text}')

    except Payment.DoesNotExist:
        print(f"ERROR: Payment record not found for tx_ref: {tx_ref}")
        return JsonResponse({'status': 'error', 'message': 'Payment record not found.'}, status=404)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Chapa API verification failed for tx_ref {tx_ref}: {e}")
        # If payment exists and is pending, mark it as failed due to verification API error
        if 'payment' in locals() and payment.status == Payment.ChapaPaymentStatusChoices.PENDING:
            payment.status = Payment.ChapaPaymentStatusChoices.FAILED
            payment.chapa_status_text = f"API Verification Error: {e}"
            payment.save()
        return HttpResponseRedirect(f'/payment-fail/?tx_ref={tx_ref}&error=api_error')
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during payment verification for tx_ref {tx_ref}: {e}")
        # Mark payment as failed due to internal error if still pending
        if 'payment' in locals() and payment.status == Payment.ChapaPaymentStatusChoices.PENDING:
            payment.status = Payment.ChapaPaymentStatusChoices.FAILED
            payment.chapa_status_text = f"Internal Error: {e}"
            payment.save()
        return HttpResponseRedirect(f'/payment-fail/?tx_ref={tx_ref}&error=internal_error')