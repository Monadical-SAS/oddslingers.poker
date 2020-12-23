from .handlers import RoutedSocketHandler


class SocketRouter:
    """
    Routes websocket messages based on message['type'] to handler functions
    defined using the @socket.route('pattern') decorator.

    Usage:
        channel_routes = [
            route_class(MyPage.router.Handler), path=r'^/mypage'),
        ]

        class MyPage(View):
            # pass an extended RoutedSocketHandler to use a Handler with more 
            #   features than the base one
            socket = SocketRouter(handler=RoutedSocketHandler)

            def props(self):
                # props given to the javascript on first pageload via 
                #   window.props
                return {'initial_data': {...}}

            @socket.connect
            def on_open(self):
                # self inside of decorated functions refers to 
                #   MyPage.socket.Handler(), not MyPage() (the socket's 
                #   view class is separate from the page's view class)
                #   the socket.Handler class can be extended by inheriting 
                #   from RoutedSocketHandler above
                self.send_json({'connected': True})

            @socket.default_route
            def default_route(self, content=None):
                action = {'details': 'Got unknown message: ' + str(content)}
                self.send_action('ERROR', action)

            @socket.route('UPDATE_USER')
            def on_update_user(self, content=None):
                ...

            @socket.route(re.compile('HELLO.*'))
            def on_hello(self, content):
                json = {
                    'received_hello': data, 
                    'on_channel_name': self.channel_name
                }
                self.send_json(json)

            @socket.disconnect
            def on_disconnect(self, message):
                disc = "spectator disconnected"
                self.broadcast_action('CHAT', recvd_message=disc)
    """

    def __init__(self, handler=None):
        BaseHandlerClass = handler or RoutedSocketHandler

        class SocketHandler(BaseHandlerClass):
            # very important, otherwise all views share all routes
            routes = list(BaseHandlerClass.routes)

        self.Handler = SocketHandler

    def route(self, pattern=None):
        """decorator to attach a request handler function to a route pattern.
        accepts route patterns as exact strings, or compiled regexes.
        """
        def wrapper(handler):
            # if any duplicate routes, last defined wins
            self.Handler.routes.append((pattern, handler))
            return handler
        return wrapper

    def set_on_handler(self, attr: str):
        """decorator to set arbitrary methods directly on the SocketHandler"""
        def wrapper(value):
            setattr(self.Handler, attr, value)
            return value
        return wrapper

    def __getattr__(self, attr: str):
        """Allow to decorate the handler directly e.g. @socket.open"""
        return self.set_on_handler(attr)

    def __setattr__(self, attr: str, value):
        """Allow to set properties directly on the SocketHandler class"""
        if attr == 'Handler':
            self.__dict__['Handler'] = value
        else:
            setattr(self.Handler, attr, value)
