from django.core.management.base import BaseCommand

from ui.views.leaderboard import save_leaderboard_cache


class Command(BaseCommand):
    help = (
        'Save the leaderboard queries than can be cached as json'
    )

    def handle(self, *args, **options):
        save_leaderboard_cache()
