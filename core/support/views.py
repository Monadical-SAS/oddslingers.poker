from typing import List

from django.contrib.auth import get_user_model

from .models import SupportTicket
from .artifacts import read_notes, read_user_info

User = get_user_model()


def support_tickets_for_user(user: User) -> List[dict]:
    if not user or user.is_anonymous:
        return []

    tickets = SupportTicket.objects\
                           .filter(reported_by=user)\
                           .order_by('-opened')

    return [
        {
            'short_id': ticket.short_id,
            'subject': ticket.subject,
            'notes': read_notes(ticket),
            'opened': ticket.opened,
            'modified': ticket.modified,
            'closed': ticket.closed,
            'status': ticket.status,
            'table_name': ticket.table.name if ticket.table else None,
            'table_path': ticket.table.path if ticket.table else None,
            'table_short_id': ticket.table.short_id if ticket.table else None,
            'reported_by_email': (
                (read_user_info(ticket) or {}).get('email')
            ),
        }
        for ticket in tickets
    ]
