from django.urls import path
from . import views
from . import admin_views
from . import payment_views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/check-user/', views.check_user_exists, name='check_user_exists'),
    path('api/resend-otp/', views.resend_otp, name='resend_otp'),
    path('signup/organizer/', views.organizer_signup, name='organizer_signup'),
    path('verify-otp/<str:email>/', views.verify_otp, name='verify_otp'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
    path('dashboard/organizer/', views.organizer_dashboard, name='organizer_dashboard'),
    path('dashboard/voter/', views.voter_dashboard, name='voter_dashboard'),
    path('accredit/<str:short_id>/', views.voter_accreditation, name='voter_accreditation'),
    path('vote/<str:short_id>/', views.cast_vote_view, name='cast_vote'),
    path('results/<str:short_id>/', views.view_election_results, name='election_results'),
    path('election/<str:short_id>/status/<str:action>/', views.update_status, name='update_status'),
    path('active-elections/', views.active_elections_list, name='active_elections'),
    
    # Grand Admin Views (from admin_views.py)
    path('grand-admin/dashboard/', admin_views.grand_admin_dashboard, name='grand_admin_dashboard'),
    path('grand-admin/approve/<int:organizer_id>/<str:action>/', admin_views.approve_organizer, name='approve_organizer'),
    path('grand-admin/analytics/', admin_views.system_analytics, name='analytics'),
    path('grand-admin/audit-logs/', admin_views.audit_logs_view, name='audit_logs'),
    path('grand-admin/toggle-otp/', admin_views.toggle_system_otp, name='toggle_system_otp'),
    path('grand-admin/toggle-receipts/', admin_views.toggle_system_receipts, name='toggle_system_receipts'),
    path('grand-admin/pricing/', admin_views.manage_plan_pricing, name='manage_plan_pricing'),
    path('grand-admin/elections/', admin_views.list_all_elections, name='list_all_elections'),
    path('grand-admin/payments/', admin_views.list_all_payments, name='list_all_payments'),
    
    # Organizer Management
    path('grand-admin/organizers/', admin_views.list_organizers, name='list_organizers'),
    path('grand-admin/organizers/<int:organizer_id>/unapprove/', admin_views.unapprove_organizer, name='unapprove_organizer'),
    path('grand-admin/organizers/<int:organizer_id>/delete/', admin_views.delete_organizer, name='delete_organizer'),
    
    # Institution Management
    path('grand-admin/institutions/', admin_views.list_institutions, name='list_institutions'),
    path('grand-admin/institutions/add/', admin_views.manage_institution, name='add_institution'),
    path('grand-admin/institutions/edit/<int:pk>/', admin_views.manage_institution, name='edit_institution'),
    path('grand-admin/institutions/delete/<int:pk>/', admin_views.delete_institution, name='delete_institution'),

    # Election Creation & Management
    path('election/create/', views.create_election, name='create_election'),
    path('election/<str:short_id>/manage/', views.manage_election, name='manage_election'),
    path('election/<str:short_id>/position/add/', views.add_position, name='add_position'),
    path('position/<int:position_id>/candidate/add/', views.add_candidate, name='add_candidate'),
    path('candidate/<int:candidate_id>/edit/', views.edit_candidate, name='edit_candidate'),
    path('candidate/<int:candidate_id>/delete/', views.delete_candidate, name='delete_candidate'),
    path('election/<str:short_id>/toggle-voting/', views.toggle_voting, name='toggle_voting'),
    path('election/<str:short_id>/toggle-receipts/', views.toggle_election_receipts, name='toggle_election_receipts'),
    path('election/<str:short_id>/export-csv/', views.export_results_csv, name='export_results_csv'),
    path('election/<str:short_id>/analytics/', admin_views.election_analytics, name='election_analytics'),
    path('election/<str:short_id>/extend-time/', views.extend_election_time, name='extend_election_time'),
    path('election/<str:short_id>/export-pdf/', views.export_results_pdf, name='export_results_pdf'),
    
    # Payment & Plans
    path('election/<str:short_id>/select-plan/', payment_views.select_plan, name='select_plan'),
    path('election/<str:short_id>/activate-free/', payment_views.activate_free_plan, name='activate_free_plan'),
    path('election/<str:short_id>/pay/', payment_views.initialize_payment, name='initialize_payment'),
    path('election/<str:short_id>/verify-payment/', payment_views.verify_payment, name='verify_payment'),
    path('paystack/webhook/', payment_views.paystack_webhook, name='paystack_webhook'),
    
    # Voter List Management
    path('election/<str:short_id>/voter-list/', views.manage_voter_list, name='manage_voter_list'),
    path('allowed-email/<int:email_id>/delete/', views.delete_allowed_email, name='delete_allowed_email'),
    
    # Sophisticated Features
    path('verify-ballot/', views.ballot_verification, name='ballot_verification'),
    path('election/<str:short_id>/nudge/', views.nudge_voters, name='nudge_voters'),
    path('election/<str:short_id>/audit-report/', admin_views.export_audit_pdf, name='export_audit_pdf'),
    path('election/<str:short_id>/war-room/', views.result_war_room, name='result_war_room'),
    path('e/<slug:slug>/', views.election_gateway, name='election_gateway'),
]

