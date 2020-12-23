from django.core.management.base import BaseCommand

from oddslingers.tasks import send_signup_email

class Command(BaseCommand):
    help = 'Send the welcome email to a given user.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, default=None)

    def handle(self, *args, **options):
        send_signup_email(username=options['username'])
