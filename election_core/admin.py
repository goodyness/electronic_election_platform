from django.contrib import admin
from .models import Institution, ElectionOrganizer, Election, Position, Candidate, Voter, AllowedEmail, Vote, OTP, AuditLog

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')

@admin.register(ElectionOrganizer)
class ElectionOrganizerAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'approved_by')
    list_filter = ('status',)

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'institution', 'status', 'start_time', 'end_time')
    list_filter = ('status', 'institution')

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'election', 'order')

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'faculty')

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ('user', 'election', 'matric_number', 'is_accredited', 'has_voted')
    list_filter = ('is_accredited', 'has_voted')

admin.site.register(AllowedEmail)
admin.site.register(Vote)
admin.site.register(OTP)
admin.site.register(AuditLog)
