from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, UserSession, UserBalance, UserStats


class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'user', 'ip', 'last_url', 'device', 'location', 'login_date', 'last_activity')
    search_fields = ('id', 'user__username', 'user__email', 'ip', 'last_url', 'device')


class CustomUserAdmin(UserAdmin):
    list_display = ('short_id', 'username', 'email', 'games_level_number', 'chips_in_play', 'badge_count', 'hands_played', 'is_robot', 'is_staff', 'is_active', 'created', 'last_url', 'last_activity')
    search_fields = ('id', 'username', 'email')
    sort_fields = ('username', 'email', 'created', 'games_level_number', 'is_robot', 'is_staff', 'is_active', 'last_url', 'last_activity')


admin.site.register(User, CustomUserAdmin)
admin.site.register(UserSession, UserSessionAdmin)
admin.site.register(UserBalance)
admin.site.register(UserStats)
