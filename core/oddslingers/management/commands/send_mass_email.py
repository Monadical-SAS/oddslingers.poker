import sys

from django.core.management.base import BaseCommand

from django.core.mail import get_connection, EmailMultiAlternatives


class Command(BaseCommand):
    help = 'Send a mass email to a list of recipients'

    def add_arguments(self, parser):
        parser.add_argument('subject', type=str)
        parser.add_argument('content_file', type=str)
        parser.add_argument('recipients_file', type=str)

    def handle(self, subject, content_file, recipients_file):
        # open SMTP connection to django email provider
        connection = get_connection()
        connection.open()

        try:
            with open(f'{content_file}.html', 'r') as f:
                html_email = f.read()

            with open(f'{content_file}.txt', 'r') as f:
                txt_email = f.read()
        except FileNotFoundError:
            print('Content must be the filename of the html & txt newsletters '
                  'e.g. if content_file is "newsletter_01", the script loads '
                  'newsletter_01.html and newsletter_01.txt as the email msg.')
            raise

        sent = 0
        with open(recipients_file, 'r') as f:
            for addr in f.read().split('\n'):
                if '@' not in addr or '.' not in addr.rsplit('@', 1)[-1]:
                    continue

                msg = EmailMultiAlternatives(
                    subject,
                    txt_email,
                    "OddSlingers Poker <hello@oddslingers.com>",
                    [addr.strip()],
                    # connection=connection,
                )
                msg.attach_alternative(html_email, "text/html")
                try:
                    msg.send()
                except Exception:
                    print(f'\nBad email: {addr.strip()}')

                sys.stdout.write('.')
                sent += 1

        connection.close()
        print(f'[√] Sent to {sent} subscribers: {subject}')
