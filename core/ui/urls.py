from channels.routing import route_class

from django.conf import settings
from django.urls import reverse, include, path
from django.views.generic.base import RedirectView
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap

from .views.pages import (
    Home, About, Table, TableEmbed, Sidebet, TournamentSummary,
    Learn, Speedtest, Support, FAQ
)

from .views.leaderboard import Leaderboard
from .views.tables import Tables

from .views.accounts import (
    UserProfile, Login, Signup, Logout, EmailChips, ChangeTheme, ConfirmEmail
)
from .views.api import (
    User, UserBalance, UserSessions, TableInvite, URLShortener,
    SupportTicketDownload, TableArchive
)
from linky.views import short_url_redirect

from poker.views.debugger import FrontendDebugger, BackendDebugger

# from .tests import StubPageForIntegrationTests


if not settings.DEBUG:
    def handler500(request):
        return render(request, '500.html', status=500)  # noqa


class StaticViewSitemap(Sitemap):
    """Sitemap used to generate sitemap.xml for search engines.
       Add any pages you want indexed by search engines to the list below.
    """
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return [
            'Home',
            'About',
            'Learn',
            'Support',
            'Speedtest',
            'Login',
            'Signup',
            'Logout',
            'Tables',
            'Sidebet',
            'Leaderboard',
            'FAQ',
        ]

    def location(self, item):
        return reverse(item)


urlpatterns = [
    path('', Home.as_view(), name='Home'),
    path('about/', About.as_view(), name='About'),
    path('learn/', Learn.as_view(), name='Learn'),
    path('speedtest/', Speedtest.as_view(), name='Speedtest'),
    path('support/', Support.as_view(), name='Support'),
    path('support/<ticket_id>/fdebugger', FrontendDebugger.as_view(), name='FrontendDebugger'),
    path('support/<ticket_id>/bdebugger', BackendDebugger.as_view(), name='BackendDebugger'),
    path('faq/', FAQ.as_view(), name='FAQ'),

    # hotfix for issue where users are getting redirected to /signup/user/<username/ after signup (which 404s)
    path('signup/user/<name>/', RedirectView.as_view(url='/user/')),
    path('accounts/signup/user/<name>/', RedirectView.as_view(url='/user/')),

    path('accounts/login/', Login.as_view(), name='Login'),
    path('accounts/signup/', Signup.as_view(), name='Signup'),
    path('accounts/logout/', Logout.as_view(), name='Logout'),
    path('accounts/confirm-email/<key>/', ConfirmEmail.as_view(), name='ConfirmEmail'),
    path('accounts/change-theme', ChangeTheme.as_view(), name='ChangeTheme'),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('hijack/', include('hijack.urls', namespace='hijack')),
    path('claim_chips/<transaction_id>', EmailChips.as_view(), name='EmailChips'),

    path('user/', UserProfile.as_view(), name='UserProfile'),
    path('user/<username>/', UserProfile.as_view(), name='UserProfile'),

    path('sidebet/', Sidebet.as_view(), name='Sidebet'),
    path('leaderboard/', Leaderboard.as_view(), name='Leaderboard'),
    path('tables/', Tables.as_view(), name='Tables'),

    path('table/', Table.as_view(), name='Table'),
    path('table/<id>/', Table.as_view(), name='Table'),
    path('table/<id>/<name>/', Table.as_view(), name='Table'),
    path('embed/<id>/', TableEmbed.as_view(), name='TableEmbed'),

    path('tournament/<id>/', TournamentSummary.as_view(), name='TournamentSummary'),

    # special shortened redirect urls
    path('s/<key>/', short_url_redirect),

    # Tools
    # path('debugger/', TableDebuggerList.as_view(), name='TableDebuggerList'),
    # path('debugger/<file_or_id>/', TableDebugger.as_view(), name='TableDebugger'),
    # path('debugger/<file_or_id>/<hand_number>/', TableDebugger.as_view(), name='TableDebugger'),
    # path('debugger/<file_or_id>/<hand_number>/<action_idx>/', TableDebugger.as_view(), name='TableDebugger'),
    # path('debugger/<file_or_id>/<hand_number>/<action_idx>/<username>/', TableDebugger.as_view(), name='TableDebugger'),

    ### API Urls
    path('api/user/', User.as_view()),
    path('api/user/balance/', UserBalance.as_view()),
    path('api/user/sessions/', UserSessions.as_view()),
    path('api/table/invite/', TableInvite.as_view()),
    path('api/table/archive/', TableArchive.as_view()),
    path('api/shorten_url/', URLShortener.as_view()),
    path('api/support/ticket/<ticket_id>/download', SupportTicketDownload.as_view(), name="SupportTicketDownload"),

    ### Integration Tests
    # path('_test/', StubPageForIntegrationTests.as_view()),
    path('start_runserver/?', RedirectView.as_view(url='/')),

    ### Redirects
    path('jobs/', RedirectView.as_view(url='https://monadical.com/team.html')),
    path('hiring/', RedirectView.as_view(url='https://monadical.com/team.html')),
    path('carreras/', RedirectView.as_view(url='https://monadical.com/team.html')),

    ### SEO
    # robots.txt is served by nginx
    # favicon.ico is served by nginx
    path('sitemap.xml', sitemap, {'sitemaps': {'static': StaticViewSitemap}}, name='django.contrib.sitemaps.views.sitemap'),
]

# Make sure to add the relevant socket routes when adding a new page to the URLS
socket_routing = [
    route_class(Table.socket.Handler, path=r'^/table/[^/]+/$'),
    route_class(TableEmbed.socket.Handler, path=r'^/embed/[^/]+/$'),
    route_class(Speedtest.socket.Handler, path=r'^/speedtest/?$'),
    route_class(Sidebet.socket.Handler, path=r'^/sidebet/$'),
    route_class(TournamentSummary.socket.Handler, path=r'^/tournament/[^/]+/$'),

    # route_class(StubPageForIntegrationTests.socket.Handler, path=r'^/_test/$'),
]


if settings.ENABLE_DEBUG_TOOLBAR or settings.ENABLE_DEBUG_TOOLBAR_FOR_STAFF:
    # serve Django Debug toolbar files
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

if settings.SERVE_STATIC:
    # serve staticfiles via runserver
    from django.contrib.staticfiles import views
    urlpatterns += [
        path('static/<path>', views.serve),
    ]
