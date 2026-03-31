from django.contrib import admin
from .models import (
    Institution, ElectionOrganizer, Election, Position, Candidate, 
    Voter, AllowedEmail, Vote, OTP, AuditLog, ElectionToken, 
    Wallet, Withdrawal, SystemConfig
)

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')

@admin.register(ElectionOrganizer)
class ElectionOrganizerAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'approved_by')
    list_filter = ('status',)

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'institution', 'status', 'start_time', 'end_time', 'is_cleared', 'accreditation_type', 'election_type')
    list_filter = ('status', 'institution', 'is_cleared', 'accreditation_type', 'election_type')
    list_editable = ('is_cleared',)

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'election', 'order')

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'faculty')

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ('user', 'election', 'matric_number', 'is_accredited', 'is_token_verified', 'has_voted')
    list_filter = ('is_accredited', 'is_token_verified', 'has_voted')

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__email', 'user__username')

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('wallet__user__email', 'account_number', 'account_name')
    list_editable = ('status',)

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'enable_otp_emails', 'enable_receipt_emails')

admin.site.register(AllowedEmail)
admin.site.register(Vote)
admin.site.register(OTP)
admin.site.register(AuditLog)
admin.site.register(ElectionToken)
