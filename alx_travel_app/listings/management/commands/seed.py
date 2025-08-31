# listings/management/commands/seed.py

import random, decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from faker import Faker
from ...models import User, Property, Booking, Payment, Review, Message

fake = Faker()


class Command(BaseCommand):
    help = 'Seed the database with fake data for testing'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing data before seeding.')
        parser.add_argument('--users', type=int, default=10, help='Number of users to create.')
        parser.add_argument('--properties', type=int, default=3, help='Number of properties per host.')
        parser.add_argument('--bookings', type=int, default=2, help='Bookings per guest.')
        parser.add_argument('--messages', type=int, default=20, help='Total messages to generate.')

    def handle(self, *args, **opts):
        if opts['clear']:
            self.stdout.write(self.style.WARNING("Clearing all seed data..."))
            Message.objects.all().delete()
            Review.objects.all().delete()
            Payment.objects.all().delete()
            Booking.objects.all().delete()
            Property.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        self.seed_users(opts['users'])
        self.seed_properties(opts['properties'])
        self.seed_bookings(opts['bookings'])
        self.seed_messages(opts['messages'])

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    def seed_users(self, count):
        roles = [User.RoleChoices.GUEST, User.RoleChoices.HOST]
        for _ in range(count):
            role = random.choice(roles)
            user = User.objects.create_user(
                email=fake.unique.email(),
                username=fake.user_name(),
                password='password123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                phone_number=fake.phone_number(),
                role=role,
            )
            if role == User.RoleChoices.HOST:
                user.is_staff = True
                user.save()
        self.stdout.write(self.style.SUCCESS(f"Created {count} users."))

    def seed_properties(self, count_per_host):
        hosts = User.objects.filter(role=User.RoleChoices.HOST)
        total = 0
        for host in hosts:
            for _ in range(count_per_host):
                Property.objects.create(
                    host=host,
                    name=fake.catch_phrase(),
                    description=fake.text(200),
                    location=fake.address(),
                    price_per_night=decimal.Decimal(random.randint(100, 1000)),
                )
                total += 1
        self.stdout.write(self.style.SUCCESS(f"Created {total} properties."))

    def seed_bookings(self, max_per_guest):
        guests = User.objects.filter(role=User.RoleChoices.GUEST)
        properties = list(Property.objects.all())
        booking_count = 0
        payment_count = 0

        for guest in guests:
            for _ in range(random.randint(1, max_per_guest)):
                prop = random.choice(properties)
                start = fake.date_between(start_date='-30d', end_date='+30d')
                end = start + timedelta(days=random.randint(1, 7))
                price = prop.price_per_night * (end - start).days
                status = random.choice(Booking.BookingStatusChoices.values)

                booking = Booking.objects.create(
                    property=prop,
                    user=guest,
                    start_date=start,
                    end_date=end,
                    total_price=price,
                    status=status,
                )
                booking_count += 1

                if status == Booking.BookingStatusChoices.CONFIRMED:
                    Payment.objects.create(
                        booking=booking,
                        amount=price,
                        payment_method=random.choice(Payment.PaymentMethodChoices.values),
                    )
                    payment_count += 1

                # Review for confirmed and past
                if status == Booking.BookingStatusChoices.CONFIRMED and end < timezone.now().date():
                    Review.objects.create(
                        property=prop,
                        user=guest,
                        rating=random.randint(1, 5),
                        comment=fake.sentence()
                    )

        self.stdout.write(self.style.SUCCESS(f"Created {booking_count} bookings."))
        self.stdout.write(self.style.SUCCESS(f"Created {payment_count} payments and related reviews."))

    def seed_messages(self, count):
        users = list(User.objects.exclude(role=User.RoleChoices.ADMIN))
        if len(users) < 2:
            self.stdout.write(self.style.WARNING("Not enough users to send messages."))
            return

        for _ in range(count):
            sender = random.choice(users)
            recipient = random.choice([u for u in users if u != sender])
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                message_body=fake.sentence()
            )

        self.stdout.write(self.style.SUCCESS(f"Created {count} messages."))
