from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from sockets.models import Socket


class Command(BaseCommand):
    help = 'List all active user sessions.'

    def handle(self, *args, **options):
        recent = timezone.now() - timezone.timedelta(minutes=2)
        active_sockets = Socket.objects.filter(active=True, last_ping__gt=recent)

        for socket in active_sockets:
            user = socket.user.username if socket.user else "anon"
            activity = (
                socket.last_ping.strftime('%h %d %H:%M')
                if socket.active else
                'inactive'
            )
            print(
                f'{user} on '
                f'{settings.BASE_URL}{socket.path} '
                f'(Last active {activity})'
            )

        raise SystemExit(bool(active_sockets))
