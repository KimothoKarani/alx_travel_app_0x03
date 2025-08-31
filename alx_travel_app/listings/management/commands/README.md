# Database Seeder Command (`seed.py`)

This Django management command is designed to populate your application's database with sample data. It's an essential tool for development, testing, and demonstrating the application without manually creating numerous records.

It generates realistic-looking data for:
*   Users
*   Properties
*   Bookings
*   Payments
*   Reviews
*   Messages

## Prerequisites

Before running this command, ensure you have:

1.  **Required Libraries:** `djangorestframework` and `Faker` installed in your virtual environment.
    ```bash
    pip install djangorestframework Faker
    ```
2.  **Applied Migrations:** Your database schema must be up-to-date with your models.
    ```bash
    python manage.py makemigrations listings
    python manage.py migrate
    ```

## Usage

Navigate to your Django project's root directory (where `manage.py` is located) and execute the command:

### Basic Command

To populate the database with default quantities of sample data:

```bash
python manage.py seed