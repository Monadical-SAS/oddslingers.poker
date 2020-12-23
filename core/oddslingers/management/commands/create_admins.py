from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model

from banker.mutations import buy_chips

from oddslingers.mutations import execute_mutations


class Command(BaseCommand):
    help = 'Create max and nick users with default passwords'

    def add_arguments(self, parser):
        parser.add_argument(
            '-f',
            '--force',
            action='store_true',
            dest='force',
            help='Create admins even when DEBUG=False',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise Exception('Can only be run on development machines!! (when DEBUG=True) or with -f')

        m = get_user_model().objects.create_user(
            username='max',
            is_staff=True,
            is_superuser=True,
            password='asdf'
        )
        execute_mutations(
            buy_chips(m, 8888888)
        )

        n = get_user_model().objects.create_user(
            username='squash',
            is_staff=True,
            is_superuser=True,
            password='sweeting'
        )
        execute_mutations(
            buy_chips(n, 8888888)
        )

        print('Created admin DEBUG users:', m, n)
