"""
General Ledger - Admin Configuration
"""
from django.contrib import admin
from .models import JournalEntry



# class JournalEntryLineInline(admin.TabularInline):
#     model = JournalEntryLine
#     extra = 2


# @admin.register(JournalEntry)
# class JournalEntryAdmin(admin.ModelAdmin):
#     list_display = ['entry_number', 'entry_date', 'company', 'fiscal_year', 'is_posted']
#     list_filter = ['company', 'fiscal_year', 'is_posted', 'entry_date']
#     search_fields = ['entry_number', 'description']
#     inlines = [JournalEntryLineInline]
