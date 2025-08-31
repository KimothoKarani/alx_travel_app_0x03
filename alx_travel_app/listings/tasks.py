from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Booking, Payment

@shared_task
def send_booking_confirmation_email(booking_id_str, recipient_email):
    """
    Sends a booking confirmation email asynchronously.
    `booking_id_str` is passed as a string because UUIDs are not directly
    JSON serializable by default with Celery, but strings are.
    """
    try:
        booking = Booking.objects.get(booking_id=booking_id_str)
        subject = f"Your Booking #{str(booking.booking_id)[:8]} is Confirmed with ALX Travel."
        message = (
            f"Dear {booking.user.first_name},\n\n"
            f"Thank you for booking with ALX Travel!\n\n"
            f"Your booking for '{booking.property.name}' "
            f"located in {booking.property.location} "
            f"from {booking.start_date} to {booking.end_date} "
            f"has been successfully confirmed.\n\n"
            f"Price per night: {booking.property.price_per_night} USD\n"
            f"Total price: {booking.total_price} USD\n\n"
            f"We look forward to hosting you!\n\n"
            f"Best regards,\n"
            f"ALX Travel Team"
        )
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(
            subject,
            message,
            from_email,
            [recipient_email],
            fail_silently=False,
        )

        print(f"DEBUG: Booking confirmation email for booking {booking_id_str} sent to {recipient_email}")
    except Booking.DoesNotExist:
        print(f"ERROR: Booking {booking_id_str} not found for email notification.")
    except Exception as e:
        print(
            f"ERROR: Failed to send booking confirmation email for booking {booking_id_str} "
            f"to {recipient_email}: {e}"
        )

@shared_task
def send_payment_confirmation_email(payment_id_str, recipient_email, amount, booking_ref):
    """
    Sends a payment confirmation email asynchronously.
    (Moved from views.py for centralized task management)
    """
    try:
        # In a real app, you might fetch the Payment object here too,
        # but for this specific task, direct parameters are fine.
        subject = f"Your Payment for Booking {booking_ref} is Confirmed!"
        message = (
            f"Dear customer,\n\n"
            f"Your payment of {amount} ETB for booking {booking_ref} "
            f"has been successfully processed. Payment ID: {payment_id_str[:8]}...\n\n"
            f"Thank you for choosing ALX Travel!\n\n"
            f"Best regards,\n"
            f"The ALX Travel Team"
        )
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(
            subject,
            message,
            from_email,
            [recipient_email],
            fail_silently=False,
        )
        print(f"DEBUG: Payment confirmation email for booking {booking_ref} (Payment ID: {payment_id_str}) sent to {recipient_email}.")
    except Exception as e:
        print(f"ERROR: Failed to send payment confirmation email for booking {booking_ref} to {recipient_email}: {e}")