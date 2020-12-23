import random, string

from typing import Optional, List, Mapping

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.http import Http404
from django.urls import reverse

from linky.models import TrackedLink
from oddslingers.settings import DEFAULT_HOST, DEFAULT_HTTP_PROTOCOL

CAMPAIGNS = [
    'facebook_table_share',
    'twitter_table_share',
]

ALLOWED_SHORTENED_VIEWS = {'Table', 'TournamentSummary'}

def create_link(viewname:str,
                args:Optional[List[str]]=None,
                kwargs:Optional[Mapping[str,str]]=None,
                campaign_name=None,
                user=None) -> str:

    assert viewname in ALLOWED_SHORTENED_VIEWS, f'Not allowed to shorten urls to view {viewname}'

    target_path = reverse(viewname, args=args, kwargs=kwargs)
    full_url = f'{DEFAULT_HTTP_PROTOCOL}://{DEFAULT_HOST}{target_path}'

    random_str = ''.join(
        random.choices(string.ascii_letters + string.digits, k=16)
    )
    link = TrackedLink(
        created_by=user,
        target_url=full_url,
        campaign=campaign_name,
        key=random_str,
    )
    link.save()

    return link.short_url()


def short_url_redirect(request, key=None):
    try:
        link = TrackedLink.objects.get(key=key)
    except ObjectDoesNotExist:
        raise Http404('Shortened url does not exist')

    link.clicks += 1
    link.save()
    return redirect(link.target_url)
