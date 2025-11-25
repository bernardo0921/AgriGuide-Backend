#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

# Fix database - clean up partial migration
python << END
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_ai.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        # Drop partial tables
        cursor.execute("DROP TABLE IF EXISTS agriguide_ai_verificationcode CASCADE")
        print("✓ Dropped agriguide_ai_verificationcode")
    except Exception as e:
        print(f"⚠ Could not drop verificationcode: {e}")
    
    try:
        cursor.execute("DROP TABLE IF EXISTS agriguide_ai_notification CASCADE")
        print("✓ Dropped agriguide_ai_notification")
    except Exception as e:
        print(f"⚠ Could not drop notification: {e}")
    
    try:
        # Reset migration state
        cursor.execute("""
            DELETE FROM django_migrations 
            WHERE app = 'agriguide_ai' AND name = '0006_verificationcode_notification'
        """)
        print("✓ Reset migration state")
    except Exception as e:
        print(f"⚠ Could not reset migration: {e}")

print("Database cleanup complete!")
END

# Now run migrations
python manage.py migrate