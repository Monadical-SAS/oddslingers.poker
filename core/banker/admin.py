from django.contrib import admin


from .models import Cashier, BalanceTransfer
from .utils import balance as get_balance


class CashierAdmin(admin.ModelAdmin):
    list_display = ('balance',  'id')

    def balance(self, obj):
        return int(get_balance(obj))


class BalanceTransferAdmin(admin.ModelAdmin):
    list_display = ('amt', 'source', 'dest', 'timestamp', 'notes')
    search_fields = ('id', 'source', 'dest', 'notes', 'timestamp')


admin.site.register(Cashier, CashierAdmin)
admin.site.register(BalanceTransfer, BalanceTransferAdmin)
