from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix database migration issues'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            try:
                # Drop the partial tables
                cursor.execute("DROP TABLE IF EXISTS agriguide_ai_verificationcode CASCADE")
                cursor.execute("DROP TABLE IF EXISTS agriguide_ai_notification CASCADE")
                self.stdout.write(self.style.SUCCESS('✓ Dropped partial tables'))
                
                # Reset migration state to 0005
                cursor.execute("""
                    DELETE FROM django_migrations 
                    WHERE app = 'agriguide_ai' AND name = '0006_verificationcode_notification'
                """)
                self.stdout.write(self.style.SUCCESS('✓ Reset migration state'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))