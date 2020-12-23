from django.contrib import admin

from .models import (
    Player,
    PokerTable,
    HandHistory,
    HandHistoryEvent,
    HandHistoryAction,
    ChatHistory,
    ChatLine,
    PokerTableStats,
    Freezeout,
    PokerTournament,
    TournamentResult,
)


class PlayerAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'username', 'table', 'seated', 'position', 'stack')

class PokerTableAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'name', 'table_type', 'tournament', 'num_seats', 'sb', 'bb', 'min_buyin', 'max_buyin', 'hand_number')
    search_fields = ('id', 'name', 'table_type', 'tournament')

class HandHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'timestamp', 'hand_number')

class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'users')

    def users(self, history):
        return ', '.join({
            str(s)
            for s in history.chatline_set.all()
                            .values_list('user__username', flat=True)    
        })


admin.site.register(Player, PlayerAdmin)
admin.site.register(PokerTable, PokerTableAdmin)

admin.site.register(HandHistory, HandHistoryAdmin)
admin.site.register(HandHistoryEvent)
admin.site.register(HandHistoryAction)

admin.site.register(ChatHistory, ChatHistoryAdmin)
admin.site.register(ChatLine)
admin.site.register(PokerTableStats)

admin.site.register(Freezeout)
admin.site.register(PokerTournament)
admin.site.register(TournamentResult)
