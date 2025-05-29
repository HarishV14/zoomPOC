from django.contrib import admin
from .models import ZoomOAuthToken

@admin.register(ZoomOAuthToken)
class ZoomOAuthTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_type', 'created_at', 'updated_at', 'is_expired')
    list_filter = ('token_type', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
