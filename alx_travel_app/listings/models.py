# alx_travel_app/listings/models.py

import uuid
from enum import unique

from django.db import models
from django.contrib.auth.models import AbstractUser  # For custom User model
from django.core.validators import MinValueValidator, MaxValueValidator

# BaseUserManager for creating custom users/superusers
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom manager for the User model to handle email as the username field.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# --- User Model ---
# Extending Django's AbstractUser to match the provided specification.
class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Includes user_id as PK, explicit email uniqueness, phone_number, and role.
    """
    # user_id: Primary Key, UUID, Indexed (overrides default 'id')
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                               editable=False)  # Removed redundant unique=True, db_index=True

    # first_name: VARCHAR, NOT NULL (overrides AbstractUser's blank=True)
    first_name = models.CharField(max_length=150, null=False, blank=False)

    # last_name: VARCHAR, NOT NULL (overrides AbstractUser's blank=True)
    last_name = models.CharField(max_length=150, null=False, blank=False)

    # email: VARCHAR, UNIQUE, NOT NULL (overrides AbstractUser's non-unique email)
    email = models.EmailField(unique=True, null=False, blank=False, verbose_name='email address')

    # password_hash: VARCHAR, NOT NULL (handled by AbstractUser's 'password' field internally)
    # No need to explicitly define 'password_hash'; Django handles it with the 'password' field.

    # phone_number: VARCHAR, NULL
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    # role: ENUM (guest, host, admin), NOT NULL
    class RoleChoices(models.TextChoices):
        GUEST = 'guest', 'Guest'
        HOST = 'host', 'Host'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=10, choices=RoleChoices.choices, default=RoleChoices.GUEST, null=False)

    # created_at: TIMESTAMP, DEFAULT CURRENT_TIMESTAMP (Explicitly defined)
    created_at = models.DateTimeField(auto_now_add=True)

    # Assign the custom manager
    objects = UserManager()  # Connect our custom manager to the User model

    # Configure AbstractUser to use 'email' for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']  # Fields required for createsuperuser

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']  # Order by our custom created_at
        indexes = [
            models.Index(fields=['email']),  # Additional index on email as per spec
        ]

    def __str__(self):
        return self.email


# No need for `CustomUser = get_user_model()` here.
# Inside this file, after `User` is defined, you can just use `User` directly.
# For other files, `from django.contrib.auth import get_user_model` and `User = get_user_model()` is the correct approach.


# --- Property Model ---
class Property(models.Model):
    """
    Represents a property listing available for booking.
    Corresponds to 'Listing' in previous iteration, renamed to 'Property' as per spec.
    """
    property_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                   editable=False)  # Removed redundant unique=True, db_index=True
    host = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='properties')  # host_id in spec - Changed to User
    name = models.CharField(max_length=255, null=False)  # Changed from 'title' to 'name'
    description = models.TextField(null=False)
    location = models.CharField(max_length=255, null=False)  # Changed from address/city/country composite
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),  # Added index for name for search performance
        ]

    def __str__(self):
        return self.name


# --- Booking Model ---
class Booking(models.Model):
    """
    Represents a booking made by a guest for a specific property.
    """
    booking_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                  editable=False)  # Removed redundant unique=True, db_index=True
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')  # property_id in spec
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='bookings')  # user_id in spec - Changed to User
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=False)

    # status: ENUM (pending, confirmed, canceled), NOT NULL
    class BookingStatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELED = 'canceled', 'Canceled'

    status = models.CharField(
        max_length=10,
        choices=BookingStatusChoices.choices,
        default=BookingStatusChoices.PENDING,
        null=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property']),  # Additional index on property
            models.Index(fields=['user']),  # Additional index on user
        ]
        # Consider adding a unique_together constraint or custom validation
        # to prevent overlapping bookings for the same property.

    def __str__(self):
        # Using user.email for consistency with USERNAME_FIELD
        return f"Booking {self.booking_id} for {self.property.name} by {self.user.email}"


# --- Payment Model ---
class Payment(models.Model):
    """
    Records payment details for a booking.
    """
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                  editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')  # booking_id in spec
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    payment_date = models.DateTimeField(auto_now_add=True)  # Matches 'TIMESTAMP, DEFAULT CURRENT_TIMESTAMP'

    # New fields for Chapa integration
    chapa_transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True, # Can be null initially before Chapa returns it
        blank=True,
        help_text="Chapa's unique transaction identifier (tx_ref or transaction_id)."
    )

    # status from Chapa's perspective
    class ChapaPaymentStatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELED = 'CANCELLED', 'Canceled' # If user cancels on Chapa's page
        REVERSED = 'REVERSED', 'Reversed' # For refunds/chargebacks

    status = models.CharField(
        max_length=10,
        choices=ChapaPaymentStatusChoices.choices,
        default=ChapaPaymentStatusChoices.PENDING,
        null=False,
        help_text="Chapa's payment status as reported by Chapa."
    )

    # Storing Chapa's specific status message/description
    chapa_status_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Chapa's payment status as reported by Chapa."
    )


    # payment_method: ENUM (credit_card, paypal, stripe), NOT NULL
    class PaymentMethodChoices(models.TextChoices):
        CHAPA = 'chapa', 'Chapa Payment Gateway'
        CREDIT_CARD = 'credit_card', 'Credit Card'
        PAYPAL = 'paypal', 'PayPal'
        STRIPE = 'stripe', 'Stripe'

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.CHAPA,
        null=False,
        help_text="The payment method or gateway used."
    )

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['booking']),  # Additional index on booking
            models.Index(fields=['chapa_transaction_id']), # For quick lookup by Chapa ID
            models.Index(fields=['status']), # For querying payment by status
        ]

    def __str__(self):
        return f"Payment {self.payment_id} for Booking {self.booking.booking_id} - {self.amount} ({self.status})"


# --- Review Model ---
class Review(models.Model):
    """
    Represents a review left by a user for a property.
    """
    review_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                 editable=False)  # Removed redundant unique=True, db_index=True
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')  # property_id in spec
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='reviews')  # user_id in spec - Changed to User
    rating = models.IntegerField(
        null=False,
        validators=[MinValueValidator(1), MaxValueValidator(5)],  # CHECK: rating >= 1 AND rating <= 5
        help_text='Rating must be between 1 and 5.'
    )
    comment = models.TextField(null=False)  # TEXT, NOT NULL (changed from previous assumption)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property']),  # Additional index on property
            models.Index(fields=['user']),  # Additional index on user
        ]
        # Optional: Ensure a user can only leave one review per property
        unique_together = ('property', 'user')

    def __str__(self):
        # Using user.email for consistency with USERNAME_FIELD
        return f"Review {self.rating}/5 for {self.property.name} by {self.user.email}"


# --- Message Model (Rectified for Threading as per previous context) ---
class Message(models.Model):
    """
    Represents a message in a threaded conversation.
    A message can be a top-level message or a reply to another message.
    """
    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                  editable=False)  # Removed redundant unique=True, db_index=True
    sender = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='sent_messages')  # sender_id in spec - Changed to User

    # Recipient can be null for replies, or removed if strictly threaded discussions
    # For a general messaging system that can be both direct and threaded, keeping recipient is fine,
    # but it will be null for messages that are purely replies in a thread.
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True,
                                  blank=True)

    message_body = models.TextField(null=False)
    sent_at = models.DateTimeField(auto_now_add=True)  # Matches 'TIMESTAMP, DEFAULT CURRENT_TIMESTAMP'

    # For threaded messages: ForeignKey to self, allows null for top-level messages
    parent_message = models.ForeignKey(
        'self',  # Refers to the Message model itself
        on_delete=models.SET_NULL,  # If parent deleted, set this message's parent to null (doesn't delete reply)
        null=True,
        blank=True,
        related_name='replies'  # This is crucial for accessing replies like `message_obj.replies.all()`
    )

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['sender', 'sent_at']),
            models.Index(fields=['recipient', 'sent_at']),  # Still useful for filtering 'to me' messages
            models.Index(fields=['parent_message']),  # Index for efficient reply lookup
        ]

    def __str__(self):
        # Using sender.email and recipient.email for consistency
        recipient_str = self.recipient.email if self.recipient else 'None'
        parent_str = f" (Reply to {self.parent_message.message_id.hex[:8]})" if self.parent_message else ""
        return f"From {self.sender.email} to {recipient_str}{parent_str}: {self.message_body[:50]}..."