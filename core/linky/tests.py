from django.test import TestCase
from django.contrib.auth import get_user_model

from oddslingers.settings import DEFAULT_HOST, DEFAULT_HTTP_PROTOCOL

from linky.views import CAMPAIGNS, create_link

from poker.models import PokerTable

class TestLinky(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cowpig',
            email='cowpig@hello.com',
            password='banana'
        )

    def test_shortened_urls(self):
        table = PokerTable.objects.create_table(name='TestLinky Table')
        table_url = f'{DEFAULT_HTTP_PROTOCOL}://{DEFAULT_HOST}{table.path}'
        for campaign in CAMPAIGNS:
            link = create_link(
                viewname='Table',
                args=[table.short_id],
                campaign_name=campaign,
                user=self.user
            )

            link = link.replace(f'{DEFAULT_HTTP_PROTOCOL}://{DEFAULT_HOST}', '')
            response = self.client.get(link)

            self.assertRedirects(response, table_url, fetch_redirect_response=False)
