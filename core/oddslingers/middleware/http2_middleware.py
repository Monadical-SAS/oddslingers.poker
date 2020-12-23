"""
Parse staticfiles used by each page and add asset preload headers to the request, 
which nginx and/or CloudFlare can use to push staticfiles upstream to HTTP/2 clients before they're requested.

Inspired by, but not a direct copy of: https://github.com/skorokithakis/django-cloudflare-push
"""

from django.conf import settings


PRELOAD_AS = {
    'js': 'script',
    'css': 'style',
    'png': 'image',
    'jpg': 'image',
    'jpeg': 'image',
    'webp': 'image',
    'svg': 'image',
    'gif': 'image',
    'ttf': 'font',
    'woff': 'font',
    'woff2': 'font'
}
PRELOAD_ORDER = {
    'css': 0,
    'ttf': 1,
    'woff': 1,
    'woff2': 1,
    'js': 2,
}
FILE_FILTER = getattr(settings, 'CLOUDFLARE_PUSH_FILTER', lambda x: True)


def record_file_to_preload(request, url):
    """save a staticfile to the list of files to push via HTTP2 preload"""
    if not hasattr(request, 'to_preload'):
        request.to_preload = set()
    request.to_preload.add(url)

def create_preload_header(urls):
    """Compose the Link: header contents from a list of urls"""
    without_vers = lambda url: url.split('?', 1)[0]
    extension = lambda  url: url.rsplit('.', 1)[-1].lower()
    preload_priority = lambda url: PRELOAD_ORDER.get(url[1], 100)

    urls_with_ext = ((url, extension(without_vers(url))) for url in urls)
    sorted_urls = sorted(urls_with_ext, key=preload_priority)

    preload_tags = (
        f'<{url}>; rel=preload; crossorigin; as={PRELOAD_AS[ext]}'
        if ext in PRELOAD_AS else
        f'<{url}>; rel=preload; crossorigin'
        for url, ext in sorted_urls
    )
    return ', '.join(preload_tags)


def HTTP2PushMiddleware(get_response):
    def middleware(request):
        """Attach a Link: header containing preload links for every staticfile 
           referenced during the request by the {% http2static %} templatetag
        """
        response = get_response(request)
        if hasattr(request, 'to_preload'):
            response['Link'] = create_preload_header(request.to_preload)
        return response
    return middleware
