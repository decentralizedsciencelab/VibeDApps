from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin for Transaction model"""
    list_display = ('tx_hash', 'method', 'status', 'block_number', 'timestamp')
    search_fields = ('tx_hash', 'method', 'from_address', 'to_address')
    list_filter = ('status', 'method')
