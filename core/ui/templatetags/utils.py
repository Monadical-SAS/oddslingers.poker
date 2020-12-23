import bleach
import json as jsonlib

from django import template
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.utils.safestring import mark_safe

from oddslingers.utils import sanitize_html, ExtendedEncoder
from oddslingers.middleware.http2_middleware import record_file_to_preload

register = template.Library()


@register.filter
def json(value):
    """safe jsonify filter, bleaches the json string using the bleach html tag remover"""
    uncleaned = jsonlib.dumps(value, cls=ExtendedEncoder)
    clean = bleach.clean(uncleaned)
    return mark_safe(clean)

@register.filter
def sanitizehtml(text):
    """allow only certain valid, whitelisted html tags, attributes, and styles"""
    return mark_safe(sanitize_html(text))

@register.filter
def striphtml(text):
    """strip all html tags from the text"""
    return mark_safe(sanitize_html(text, strip=True))

@register.simple_tag(takes_context=True)
def http2static(context, path, version=None):
    """
    same as static templatetag, except it saves the list of files used
    to request.to_preload in order to push them up to the user
    before they request it using HTTP2 push via the HTTP2PushMiddleware
    """
    url = f'{static(path)}?v={version}' if version else static(path)
    record_file_to_preload(context['request'], url)
    return url


@register.simple_tag(takes_context=True)
def theme_option(context, light_option=None, dark_option=None):
    if light_option is None or dark_option is None:
        raise ValueError('parameters cannot be None')

    request = context['request']
    user = request.user
    if user.is_authenticated:
        if user.light_theme:
            return light_option
        return dark_option
    else:
        theme_option = site_theme(request)
        if theme_option == 'light':
            return light_option
        return dark_option


def site_theme(request):
    """
    gets theme option throught cookies for non logged in users
    """
    theme_cookie = request.COOKIES.get('theme', '')
    if not theme_cookie:
        theme_cookie = 'light'
    return theme_cookie
