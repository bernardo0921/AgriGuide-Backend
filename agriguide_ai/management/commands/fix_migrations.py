from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix partial migration issues'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Drop partial tables
            cursor.execute("DROP TABLE IF EXISTS agriguide_ai_verificationcode CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS agriguide_ai_notification CASCADE;")
            self.stdout.write(self.style.SUCCESS('Dropped partial tables'))