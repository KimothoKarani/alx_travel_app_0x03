# alx_travel_app/listings/serializers.py
from random import choice

from rest_framework import serializers
from .models import User, Property, Booking, Message, Review, Payment

# --- Helper Serializers for Nested Relationships ---

class NestedUserSerializer(serializers.ModelSerializer):
    """
    Nested serializer for displaying basic user details (used in other serializers).
    """
    user_id = serializers.UUIDField(read_only=True, help_text="Unique identifier of the user.")
    first_name = serializers.CharField(read_only=True, help_text="The first name of the user.")
    last_name = serializers.CharField(read_only=True, help_text="The last name of the user.")
    email = serializers.EmailField(read_only=True, help_text="The email address of the user.")

    class Meta:
        model = User
        fields = ['user_id', 'first_name', 'last_name', 'email']
        read_only_fields = fields


class NestedPropertySerializer(serializers.ModelSerializer):
    """
    Nested serializer for displaying basic property details.
    """
    property_id = serializers.UUIDField(read_only=True, help_text="Unique identifier of the property.")
    name = serializers.CharField(read_only=True, help_text="The name of the property listing.")
    location = serializers.CharField(read_only=True, help_text="Location of the property.")
    price_per_night = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text="The price per night for booking this property."
    )

    class Meta:
        model = Property
        fields = ['property_id', 'name', 'location', 'price_per_night']
        read_only_fields = fields


# --- Main Serializers ---

class PropertySerializer(serializers.ModelSerializer):
    """
    Serializer for creating and retrieving property listings.
    """
    host = NestedUserSerializer(read_only=True, help_text="Details of the host (read-only).")
    host_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='host',
        write_only=True,
        help_text="UUID of the user who owns this property."
    )
    name = serializers.CharField(help_text="The name of the property listing.")
    description = serializers.CharField(help_text="Detailed description of the property.")
    location = serializers.CharField(help_text="Location/address of the property.")
    price_per_night = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Nightly rental price for the property."
    )
    created_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the property was created.")
    updated_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the property was last updated.")

    class Meta:
        model = Property
        fields = [
            'property_id', 'host', 'host_id', 'name', 'description',
            'location', 'price_per_night', 'created_at', 'updated_at'
        ]
        read_only_fields = ['property_id', 'created_at', 'updated_at']


class BookingSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and retrieving bookings.
    """
    property = NestedPropertySerializer(read_only=True, help_text="Details of the booked property (read-only).")
    user = NestedUserSerializer(read_only=True, help_text="Details of the guest making the booking (read-only).")

    # Only property_id should be provided by the client
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(),
        source='property',
        write_only=True,
        help_text="UUID of the property being booked."
    )

    start_date = serializers.DateField(help_text="The start date of the booking.")
    end_date = serializers.DateField(help_text="The end date of the booking.")

    # Automatically calculated
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text="Total calculated price for the entire booking duration."
    )
    status = serializers.CharField(read_only=True, help_text="Current status of the booking (pending, confirmed, or canceled).")
    created_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the booking was created.")

    class Meta:
        model = Booking
        fields = [
            'booking_id', 'property', 'property_id', 'user',
            'start_date', 'end_date', 'total_price', 'status', 'created_at'
        ]
        read_only_fields = ['booking_id', 'property', 'user', 'total_price', 'status', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for sending and retrieving direct messages between users.
    """
    sender = NestedUserSerializer(read_only=True, help_text="Details of the sender (read-only).")
    receiver = NestedUserSerializer(read_only=True, help_text="Details of the recipient (read-only).")
    parent_message = serializers.SerializerMethodField(read_only=True, help_text="ID of the parent message if this is a reply.")
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        help_text="UUID of the user sending the message."
    )
    receiver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        help_text="UUID of the message recipient."
    )
    parent_message_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
        help_text="Optional UUID of the parent message when replying."
    )
    message_body = serializers.CharField(help_text="Content of the message being sent.")
    sent_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the message was sent.")
    is_read = serializers.BooleanField(read_only=True, help_text="Indicates if the message has been read.")
    edited = serializers.BooleanField(read_only=True, help_text="Indicates if the message has been edited.")
    edited_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the message was last edited.")

    class Meta:
        model = Message
        fields = [
            'message_id', 'sender', 'sender_id', 'receiver', 'receiver_id',
            'parent_message', 'parent_message_id', 'message_body',
            'sent_at', 'is_read', 'edited', 'edited_at'
        ]
        read_only_fields = ['message_id', 'sender', 'receiver', 'parent_message', 'sent_at', 'is_read', 'edited', 'edited_at']

    def get_parent_message(self, obj):
        return str(obj.parent_message.message_id) if hasattr(obj, 'parent_message') and obj.parent_message else None


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and retrieving property reviews.
    """
    property = PropertySerializer(read_only=True, help_text="Details of the property being reviewed (read-only).")
    user = NestedUserSerializer(read_only=True, help_text="Details of the user leaving the review (read-only).")
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(),
        write_only=True,
        help_text="UUID of the property being reviewed."
    )
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        help_text="UUID of the user leaving the review."
    )
    rating = serializers.IntegerField(help_text="Rating for the property (1 to 5).")
    comment = serializers.CharField(help_text="Detailed review comment about the property.")
    created_at = serializers.DateTimeField(read_only=True, help_text="Timestamp when the review was created.")

    class Meta:
        model = Review
        fields = [
            'review_id', 'property', 'property_id', 'user', 'user_id',
            'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['review_id', 'property', 'user', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for recording and retrieving payment details.
    Updated for Chapa Integration.
    """
    booking = BookingSerializer(read_only=True, help_text="Details of the related booking (read-only).")
    booking_id = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.all(),
        write_only=True,
        help_text="UUID of the booking for which the payment is made."
    )
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Amount paid for the booking.")
    payment_date = serializers.DateTimeField(read_only=True, help_text="Timestamp when the payment was recorded.")
    payment_method = serializers.ChoiceField(
        choices=Payment.PaymentMethodChoices.choices,
        help_text="Payment method used (Chapa, credit_card, PayPal, or Stripe)."
    )

    # New fields
    chapa_transaction_id = serializers.CharField(
        read_only=True,
        help_text="Chapa's unique transaction id (read-only)."
    )
    status = serializers.ChoiceField(
        choices=Payment.ChapaPaymentStatusChoices.choices,
        read_only=True, # Status is updated by the system based on Chapa responses
        help_text="The status of the payment (PENDING, COMPLETED, FAILED, etc.)."
    )
    chapa_status_text = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text="Detailed status message from Chapa."
    )

    class Meta:
        model = Payment
        fields = [
            'payment_id', 'booking', 'booking_id', 'amount', 'payment_date',
            'payment_method', 'chapa_transaction_id', 'status', 'chapa_status_text'
        ]
        read_only_fields = [
            'payment_id', 'booking', 'payment_date',
            'chapa_transaction_id', 'status', 'chapa_status_text' # All chapa related fields are read-only from API consumer perspective
        ]