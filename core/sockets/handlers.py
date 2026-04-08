import ipaddress
import json
import logging

from typing import List, Tuple, Union

from django.conf import settings
from django.utils import timezone

from channels.generic.websocket import WebsocketConsumer

from oddslingers.utils import ANSI, debug_print_io, log_io_message
from .models import Socket
from .constants import (
    PING_RESPONSE_TYPE,
    HELLO_TYPE,
    GOT_HELLO_TYPE,
    RECONNECT_TYPE,
    TIME_SYNC_TYPE,
    ROUTING_KEY,
)

logger = logging.getLogger("sockets")

# Pre-parsed at module load so _is_trusted_proxy avoids re-parsing on every connect.
# Union covers both IPv4Network and IPv6Network (ip_network() returns either).
_TRUSTED_NETWORKS: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = [
    ipaddress.ip_network(cidr, strict=False)
    for cidr in getattr(settings, "TRUSTED_PROXY_CIDRS", [])
]


def _is_trusted_proxy(ip_str: str) -> bool:
    """Return True if ip_str falls within any TRUSTED_PROXY_CIDRS network."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _TRUSTED_NETWORKS)


class RoutedSocketHandler(WebsocketConsumer):
    """All the methods and attributes available to every websocket request.

    Ported from Channels 1.x JsonWebsocketConsumer to Channels 4 WebsocketConsumer.
    AuthMiddlewareStack in asgi.py populates scope["user"] and scope["session"].
    """

    # by default, dont require user to be logged in to get messages
    login_required: bool = False
    socket: Socket = None

    # Matching is exact string equality — regex patterns are NOT supported and will
    # silently fall through to on_unknown_receive. Add shared handlers here:
    routes: Tuple[Tuple[str, str], ...] = (
        (PING_RESPONSE_TYPE, "on_ping"),
        (HELLO_TYPE, "on_hello"),
        (TIME_SYNC_TYPE, "on_time_sync"),
    )

    @property
    def view_name(self):
        return self.__class__.__name__

    @property
    def user(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            return None
        return user

    def setup_session(self, extra: dict = None):
        """initialize the socket DB model which persists the socket info"""
        extra = extra or {}
        self.socket, created = Socket.objects.update_or_create(
            channel_name=self.channel_name,
            defaults={
                "user": self.user,
                "path": self.scope.get("path", ""),
                "active": True,
                "last_ping": timezone.now(),
                **extra,
            },
        )

    def connect(self):
        """called when the socket connects"""
        client = self.scope.get("client")
        connecting_ip = client[0] if client else None

        # Take the first X-Real-IP header only (avoid last-write-wins on duplicates).
        real_ip_header = next(
            (v for k, v in self.scope.get("headers", []) if k == b"x-real-ip"),
            None,
        )
        if (
            real_ip_header is not None
            and connecting_ip
            and _is_trusted_proxy(connecting_ip)
        ):
            # Only honour X-Real-IP when the TCP connection comes from a
            # known reverse proxy; otherwise the header is client-forged.
            if isinstance(real_ip_header, bytes):
                real_ip_header = real_ip_header.decode()
            candidate = real_ip_header.strip().split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                user_ip = candidate
            except ValueError:
                user_ip = connecting_ip
        else:
            user_ip = connecting_ip

        try:
            self.setup_session({"user_ip": user_ip})
        except Exception:
            logger.exception("Failed to initialise socket session on connect")
            # Do NOT call self.close() before accept() — undefined in Channels 4.
            # Returning without accept() causes the ASGI server to reject the handshake.
            # accept() is never reached here, so disconnect() will NOT be called by the
            # ASGI server — this block is the sole cleanup path.
            if self.socket is not None:
                try:
                    self.socket.delete()
                except Exception:
                    logger.exception(
                        "Failed to delete partial socket row on connect failure"
                    )
                finally:
                    self.socket = None
            return
        self.accept()
        if not self.check_authentication():
            # accept() has been called — disconnect() may or may not fire depending on
            # transport. Explicitly clean up the socket row to avoid orphaned DB state.
            if self.socket is not None:
                try:
                    self.socket.delete()
                except Exception:
                    logger.exception("Failed to delete socket row after auth rejection")
                finally:
                    self.socket = None
            return

    def disconnect(self, close_code):
        """called when the socket disconnects"""
        if self.socket is None:
            return
        user_ip = self.socket.user_ip
        created = self.socket.created
        last_ping = self.socket.last_ping
        now = timezone.now()
        self.socket.delete()

        if close_code == 1006:
            details = {
                "code": close_code,
                "path": self.scope.get("path", ""),
                "socket_age": (
                    str(last_ping - created) if last_ping and created else None
                ),
                "time_since_last_ping": str(now - last_ping) if last_ping else None,
                "user_id": self.user.id if self.user else None,
                "user_ip": user_ip,
                "username": self.user.username if self.user else "anon",
            }
            print(f"{ANSI['red']}[!] Dropped websocket connection!{ANSI['reset']}")
            if settings.DEBUG:
                print("\n".join(f"{k}: {v}" for k, v in details.items()))
            else:
                logger.warning(
                    "Dropped websocket due to bad network, nginx restart, or overloaded server.",
                    extra=details,
                )

    def receive(self, text_data=None, bytes_data=None):
        """called when the socket sends a message"""
        if text_data is None:
            return
        try:
            content = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Received invalid JSON from websocket")
            return

        self.log_message(out=False, content=content)
        log_io_message(self, direction="in", content=content)
        self.on_receive(content)

    def send_action(self, action_type: str, **kwargs):
        """send a websocket action with the given type and args to the user"""
        if self.socket is not None:
            self.socket.send_action(action_type=action_type, **kwargs)

    def check_authentication(self, content=None):
        """ensure the user is authorized for the given websocket message"""
        if self.login_required and not (self.user and self.user.is_authenticated):
            self.send(text_data=json.dumps({"type": RECONNECT_TYPE}))
            self.close()
            return False
        return True

    def on_receive(self, content: dict):
        """Route incoming messages to the appropriate handler."""
        if not self.check_authentication(content):
            return

        msg_type = content.get(ROUTING_KEY)
        if msg_type is None:
            logger.warning("Received message without routing key: %s", content)
            return

        for route_type, handler in self.routes:
            if route_type == msg_type:
                if callable(handler):
                    handler(content)
                else:
                    getattr(self, handler)(content)
                return

        self.on_unknown_receive(content)

    def on_unknown_receive(self, content: dict):
        """Handle unknown message types. Override in subclasses."""
        self.log_message(out=False, content=content, unknown=True)

    def on_ping(self, content: dict):
        # Inbound PING is a heartbeat ack from the frontend — update last_ping only.
        # Do NOT echo back: PING_RESPONSE_TYPE == PING_TYPE == 'PING', so replying
        # would cause an infinite ping-pong loop with the JS client.
        if self.socket is not None:
            self.socket.last_ping = timezone.now()
            self.socket.active = True
            self.socket.save(update_fields=["last_ping", "active"])

    def on_hello(self, content: dict):
        self.send_action(GOT_HELLO_TYPE)
        if self.socket is not None:
            self.socket.cleanup_stale()

    def on_time_sync(self, content: dict):
        import time

        self.send_action(TIME_SYNC_TYPE, server_time=time.time())

    def log_message(
        self, out: bool = True, content: dict = None, unknown: bool = False
    ):
        debug_print_io(out=out, content=content, unknown=unknown)
