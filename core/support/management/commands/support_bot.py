import sys

from django.core.management.base import BaseCommand
from django.conf import settings

from zulip_bots.run import main

from typing import Any, Dict

from support.models import SupportTicket
from support.incidents import send_ticket_reply


USAGE = '''
There are several commands to use this bot:
- @support help -> To show all commands the bot supports.
- @support reply -> To send a reply to a given support ticket
- @support close/open -> To close or open a given support ticket
'''

class SupportBotHandler(object):
    META = {
        'name': 'Support Ticket',
        'description': 'Relays Support Ticket communication to Zulip',
    }

    def usage(self) -> str:
        return USAGE

    def handle_message(self, message: Dict[str, str], bot_handler: Any) -> None:
        try:
            bot_response = do_support_action(message)
            bot_handler.send_reply(message, bot_response)
        except Exception as e:
            bot_handler.send_reply('Error. {}.'.format(e), bot_response)


handler_class = SupportBotHandler


class Command(BaseCommand):
    help = 'Start a zulip bot for support'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--config-file',
                            type=str,
                            required=False,
                            default=f'{settings.REPO_DIR}/etc/zulip/support_bot.ini')

    def handle(self, *args, **kwargs):
        if settings.ENABLE_SUPPORT_BOT:
            # Rather than fork and spawn a new process for the zulip bot server,
            # we import its main() and run it in our current management command thread
            # by tricking it into thinking it's being called from the command line with fresh args
            sys.argv = ['', __file__, '-c', kwargs['config_file']]
            sys.exit(main())
        else:
            raise Exception('Not launching because Support Bot is disabled.')


def do_support_action(message: Dict[str, str]) -> str:
    required_keys = {'type', 'display_recipient', 'subject', 'content', 'sender_email', 'timestamp'}
    if not required_keys.issubset(message):
        return 'Can not process your request: Missing data'

    if (not message['type'] == 'stream'
        or not message['display_recipient'] == 'support'):
            return misc_action(message)

    content = message['content'].strip()
    if content == '' or content.startswith('help'):
        return USAGE

    ticket_id = message['subject'].split(':', 1)[0]
    if not ticket_id:
        return 'I couldn\'t find the ticket ID in the topic'

    ticket = get_ticket(ticket_id)
    if not ticket:
        return f'Sorry, I couldn\'t find ticket {ticket_id}'

    command = content.split(' ', 1)[0]

    if command in ('open', 'close'):
        set_ticket_status(ticket, status=command)
        ticket_url = f'[{ticket.short_id}]({ticket.admin_url})'
        return f'I changed the  status of ticket {ticket_url} to {command}'

    if command == 'status':
        return f'Ticket is {ticket.status}'

    if command == 'reply':
        reply_text = content.replace(command, '').strip()
        if send_ticket_reply(ticket, reply_text):
            return f'I\'ve sent that message for you'
        else:
            return f'I failed you, my lord'

    return USAGE

def get_ticket(ticket_id: str) -> SupportTicket:
    try:
        return SupportTicket.objects.get(id__startswith=ticket_id)
    except (SupportTicket.MultipleObjectsReturned, SupportTicket.DoesNotExist):
        return None

def set_ticket_status(ticket: SupportTicket, status: str):
    ticket.status = status
    ticket.save()

def misc_action(message: Dict[str, str]) -> str:
    import random
    from datetime import datetime
    n = datetime.now()
    RESPONSES = [
        f'It is {n.strftime("%I:%M %p")} here where I live',
        f'Today is {n.strftime("%A")} for me',
        f'This month\'s name is {n.strftime("%B")}',
        f'I like owls :owl:',
    ]
    content = message['content'].strip()
    mates = ['Max', 'Nick', 'Ana', 'Milton', 'Juan', 'Jose', 'Jerry']
    if content.startswith('rand'):
        data = content.split(' ')
        try:
            if len(data) == 3:
                return f'{random.randint(int(data[1]), int(data[2]))}'
            elif len(data) == 2:
                return f'{random.randint(0, int(data[1]))}'
            elif len(data) == 1:
                return f'{random.choice(mates)}'
        except (ValueError, TypeError):
            pass
    if content.startswith('shuffle'):
        random.shuffle(mates)
        return f'{mates}'
    if content.lower().startswith(('hi', 'hello', 'hola', 'hey')):
        return f'Hello {message["sender_full_name"]}. I am your support.'

    return random.choice(RESPONSES)
