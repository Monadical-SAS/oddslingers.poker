import logging

from django.views import View
from django.conf import settings
from django.template import loader
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse

from oddslingers.models import UserSession
from oddslingers.utils import ExtendedEncoder

from poker.constants import TournamentStatus



logger = logging.getLogger()


class HttpResponseWithCallback(HttpResponse):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        self.callback = kwargs.pop('callback')
        super().__init__(*args, **kwargs)

    def close(self):
        """Trigger a callback after sending the response to the client
        Good for deferring expensive processing that can be done later without
        holding up the response to the client.
        """
        super().close()
        self.callback(request=self.request, response=self)


class APIView(View):
    def respond(self, data=None, errors=None, **kwargs):
        response = {
            'success': not errors,
            'errors': errors or [],
            **(data or {}),
        }
        if errors and 'status' not in kwargs:
            kwargs = {**kwargs, 'status': 500}

        return JsonResponse(response, encoder=ExtendedEncoder, **kwargs)

class BaseView(View):
    title = None               # type: str
    template = 'ui/base.html'  # type: str
    component = None           # type: str
    custom_stylesheet = None   # type: str
    login_required = False     # type: bool

    def user_json(self, request):
        user = request.user
        if not user.is_authenticated:
            return None

        return user.__json__()

    def after_response(self, request=None, response=None):
        if request.user.is_authenticated:
            UserSession.update_from_request(request)

    def get_active_tables(self, request):
        user = request.user
        if user.is_authenticated:
            table_filter = {'seated': True}

            tables_data = [
                {
                    'name': p.table.name,
                    'path': p.table.path,
                    'class': 'tournament' if p.table.tournament is not None else '',
                    'inactive_class': 'inactive' if p.table.hotness_level < 1 else ''
                } for p in user.player_set.filter(**table_filter)\
                                          .order_by('-modified')\
                                          .only('table__name',
                                                'table__modified',
                                                'table__tournament')
            ]

            tournaments_data = [
                {
                    'name': tourney.name,
                    'path': tourney.path,
                    'class': 'tournament',
                    'inactive_class': ''
                } for tourney in user.tournaments.filter(
                    status=TournamentStatus.PENDING.value
                ).order_by('-modified').only('name', 'modified')
            ]

            return [
                *tables_data,
                *tournaments_data,
            ]

        return []

    def get_base_context(self, request, *args, **kwargs):
        """get the base context items made available to every template"""

        # e.g. SHOW_VIDEO_STREAMS, ENABLE_SENTRY, etc.
        body_classes = [
            flag for flag, enabled in settings.FEATURE_FLAGS.items() if enabled
        ]

        return {
            'DEBUG': settings.DEBUG,
            # SHA is used to tell sentry which release is running on prod
            'GIT_SHA': settings.GIT_SHA,
            # refers to which set of database settings are used (aka which env is active)
            'ENVIRONMENT': settings.ODDSLINGERS_ENV,
            'TIME_ZONE': settings.TIME_ZONE,
            'LANGUAGE_CODE': settings.LANGUAGE_CODE,
            'ENABLE_SENTRY': settings.ENABLE_SENTRY,
            'SENTRY_JS_URL': settings.SENTRY_JS_URL,
            'ENABLE_PIWIK': settings.ENABLE_PIWIK,
            'PIWIK_SETUP': settings.PIWIK_SETUP,
            'ENABLE_HOTLOADING': settings.ENABLE_HOTLOADING,
            'SHOW_VIDEO_STREAMS': settings.SHOW_VIDEO_STREAMS,
            'SIGNUP_BONUS': settings.SIGNUP_BONUS,
            'user': self.user_json(request) or request.user,
            'active_tables': self.get_active_tables(request),
            'title': self.title or self.__class__.__name__,
            'page_id': self.__class__.__name__.lower(),
            'component': self.component,
            'custom_stylesheet': self.custom_stylesheet,
            'body_classes': ' '.join(body_classes),
        }

    def context(self, request, *args, **kwargs):
        """override this in your view to provide extra template context"""
        return {}

    def get_context(self, request, *args, **kwargs):
        """
            assemble the full context dictionary needed to render the
            template (base context + page context)
        """
        context = self.get_base_context(request, *args, **kwargs)
        # the variables used to render the django template

        # update context from View class's context function or attribute
        #   if context is a function, call it to get the dictionary
        #   of actual values
        if hasattr(self.context, '__call__'):
            page_context = self.context(request, *args, **kwargs)
        # if it's alaready a dictionary or property, just use it normally
        elif hasattr(self.context, '__getitem__'):
            page_context = self.context
        else:
            raise TypeError('View.context must be a dictionary or function')
        context.update(page_context)

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context(request, *args, **kwargs)

        content = loader.render_to_string(self.template, context, request)
        return HttpResponseWithCallback(content, request=request, callback=self.after_response)


class PublicReactView(BaseView):
    template = 'ui/react_base.html'
    component = 'pages/base.js'
    login_required = False

    def get_base_props(self, request, *args, **kwargs):
        base_props = {
            'url_name': request.resolver_match.url_name,
            'url': request.build_absolute_uri(),
            'domain': request.META.get('HTTP_HOST', ''),
            'view': '.'.join((self.__module__, self.__class__.__name__)),
            'DEBUG': settings.DEBUG,
            # used to tell sentry which release is running on prod
            'GIT_SHA': settings.GIT_SHA,
            # refers to which set of database settings are used (aka which env is active)
            'ENVIRONMENT': settings.ODDSLINGERS_ENV,
            'TIME_ZONE': settings.TIME_ZONE,
            'SHOW_VIDEO_STREAMS': settings.SHOW_VIDEO_STREAMS,
            'SIGNUP_BONUS': settings.SIGNUP_BONUS,
            'user': self.user_json(request),
        }

        return base_props

    def props(self, request, *args, **kwargs):
        """override this in your view to provide extra component props"""
        return {}

    def get_props(self, request, *args, **kwargs):
        # a dict passed to react code
        props = self.get_base_props(request, *args, **kwargs)
        # update props from View class's props function or attribute

        if hasattr(self.props, '__call__'):
            page_props = self.props(request, *args, **kwargs)
        elif hasattr(self.props, '__getitem__'):
            page_props = self.props
        else:
            raise TypeError('View.context must be a dictionary or function')
        props.update(page_props)

        return props

    def get(self, request, *args, **kwargs):
        props = self.get_props(request, *args, **kwargs)
        if request.GET.get('props_json'):
            return JsonResponse(props, encoder=ExtendedEncoder)

        context = self.get_context(request, *args, **kwargs)
        context['props'] = props

        content = loader.render_to_string(self.template, context, request)
        return HttpResponseWithCallback(content, request=request, callback=self.after_response)


class ReactView(LoginRequiredMixin, PublicReactView):
    login_url = settings.LOGIN_URL
    login_required = True
