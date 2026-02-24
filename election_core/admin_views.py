from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models
from django.core.paginator import Paginator
from .models import ElectionOrganizer, Election, Institution, Voter, AuditLog
from .forms import InstitutionForm

def grand_admin_dashboard(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    pending_organizers = ElectionOrganizer.objects.filter(status='PENDING_APPROVAL')
    active_institutions = Institution.objects.all()
    all_elections = Election.objects.all().order_by('-created_at')
    
    from .models import SystemConfig, PlanPricing, ElectionPayment
    config = SystemConfig.get_config()
    plans = PlanPricing.get_all_plans()
    payment_history = ElectionPayment.objects.filter(is_verified=True).order_by('-paid_at')[:5]
    all_elections = Election.objects.all().order_by('-created_at')[:5]
    
    return render(request, 'election_core/grand_admin_dashboard.html', {
        'pending_organizers': pending_organizers,
        'institutions': active_institutions,
        'elections': all_elections,
        'config': config,
        'plans': plans,
        'payment_history': payment_history
    })

def approve_organizer(request, organizer_id, action):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    organizer = get_object_or_404(ElectionOrganizer, id=organizer_id)
    if action == 'approve':
        organizer.status = 'APPROVED'
        organizer.approved_by = request.user
        messages.success(request, f"Organizer {organizer.user.get_full_name()} approved.")
        
        from .tasks import send_organizer_approval_email_task
        from django.urls import reverse
        
        dashboard_url = request.build_absolute_uri(reverse('organizer_dashboard'))
        send_organizer_approval_email_task.delay(
            organizer.user.email,
            organizer.user.get_full_name(),
            dashboard_url
        )
    elif action == 'reject':
        organizer.status = 'REJECTED'
        messages.warning(request, f"Organizer {organizer.user.get_full_name()} rejected.")
    
    from .utils import log_action
    log_action(request.user, f"Organizer Approval: {action} for {organizer.user.email}", request)
    organizer.save()
    return redirect('grand_admin_dashboard')

def system_analytics(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    from .models import AllowedEmail
    from django.db.models import Count
    total_elections = Election.objects.count()
    total_voters = AllowedEmail.objects.count()
    total_accredited = Voter.objects.filter(is_accredited=True).count()
    total_votes_cast = Voter.objects.filter(has_voted=True).count()
    
    all_elections = Election.objects.all().order_by('-created_at')
    
    faculty_turnout = Voter.objects.values('faculty').annotate(
        total=Count('id'),
        voted=Count('id', filter=models.Q(has_voted=True))
    )
    
    dept_turnout = Voter.objects.values('department').annotate(
        total=Count('id'),
        voted=Count('id', filter=models.Q(has_voted=True))
    )
    
    return render(request, 'election_core/analytics.html', {
        'total_elections': total_elections,
        'total_voters': total_voters,
        'total_accredited': total_accredited,
        'total_votes_cast': total_votes_cast,
        'faculty_turnout': faculty_turnout,
        'dept_turnout': dept_turnout,
        'all_elections': all_elections
    })

def election_analytics(request, short_id):
    from django.db.models import Count
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser or request.user.role == 'ORGANIZER'):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    election = get_object_or_404(Election, short_id=short_id)
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser or election.organizer.user == request.user):
        messages.error(request, "Access denied.")
        return redirect('home')

    from .models import AllowedEmail
    total_voters_count = AllowedEmail.objects.filter(election=election).count()
    accredited_voters_count = Voter.objects.filter(election=election, is_accredited=True).count()
    total_votes_cast = Voter.objects.filter(election=election, has_voted=True).count()
    
    voter_list = Voter.objects.filter(election=election).order_by('user__last_name')
    search_query = request.GET.get('q')
    if search_query:
        voter_list = voter_list.filter(
            models.Q(user__first_name__icontains=search_query) |
            models.Q(user__last_name__icontains=search_query) |
            models.Q(user__email__icontains=search_query) |
            models.Q(matric_number__icontains=search_query)
        )
    
    paginator = Paginator(voter_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    plan = election.plan
    hourly_participation = []
    
    if plan in ['STANDARD', 'PREMIUM']:
        from .models import Vote
        from django.db.models.functions import TruncHour
        hourly_participation = Vote.objects.filter(election=election)\
            .annotate(hour=TruncHour('timestamp'))\
            .values('hour')\
            .annotate(count=Count('id'))\
            .order_by('hour')
            
    context = {
        'election': election,
        'total_voters': total_voters_count,
        'accredited_count': accredited_voters_count,
        'voted_count': total_votes_cast,
        'page_obj': page_obj,
        'search_query': search_query,
        'plan': plan,
    }

    if plan != 'FREE':
        faculty_turnout = Voter.objects.filter(election=election).values('faculty').annotate(
            total=Count('id'),
            voted=Count('id', filter=models.Q(has_voted=True))
        )
        dept_turnout = Voter.objects.filter(election=election).values('department').annotate(
            total=Count('id'),
            voted=Count('id', filter=models.Q(has_voted=True))
        )
        context.update({
            'faculty_turnout': faculty_turnout,
            'dept_turnout': dept_turnout,
        })
    
    if plan in ['STANDARD', 'PREMIUM']:
        hourly_labels = [h['hour'].strftime('%H:00') for h in hourly_participation]
        hourly_counts = [h['count'] for h in hourly_participation]
        context.update({
            'hourly_labels': hourly_labels,
            'hourly_counts': hourly_counts,
        })

    return render(request, 'election_core/election_analytics.html', context)

def audit_logs_view(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    logs_list = AuditLog.objects.all().order_by('-timestamp')
    paginator = Paginator(logs_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'election_core/audit_logs.html', {'page_obj': page_obj})

def list_institutions(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
    
    institutions = Institution.objects.all().order_by('-created_at')
    return render(request, 'election_core/institutions.html', {'institutions': institutions})

def manage_institution(request, pk=None):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
    
    institution = get_object_or_404(Institution, pk=pk) if pk else None
    
    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=institution)
        if form.is_valid():
            form.save()
            messages.success(request, f"Institution {'updated' if pk else 'added'} successfully.")
            return redirect('list_institutions')
    else:
        form = InstitutionForm(instance=institution)
    
    return render(request, 'election_core/institution_form.html', {
        'form': form,
        'is_edit': bool(pk)
    })

def delete_institution(request, pk):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
    
    institution = get_object_or_404(Institution, pk=pk)
    institution.delete()
    messages.success(request, "Institution deleted successfully.")
    return redirect('list_institutions')

def list_organizers(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    organizer_list = ElectionOrganizer.objects.all().select_related('user', 'user__institution').order_by('-user__date_joined')
    
    search_query = request.GET.get('q')
    if search_query:
        organizer_list = organizer_list.filter(
            models.Q(user__first_name__icontains=search_query) |
            models.Q(user__last_name__icontains=search_query) |
            models.Q(user__email__icontains=search_query) |
            models.Q(user__institution__name__icontains=search_query)
        )
        
    paginator = Paginator(organizer_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'election_core/organizers.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })

def unapprove_organizer(request, organizer_id):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    organizer = get_object_or_404(ElectionOrganizer, id=organizer_id)
    organizer.status = 'PENDING_APPROVAL'
    organizer.save()
    
    from .utils import log_action
    log_action(request.user, f"Revoked Approval: Organizer {organizer.user.email}", request)
    
    messages.warning(request, f"Approval revoked for {organizer.user.get_full_name()}. Status set to Pending.")
    return redirect('list_organizers')

def delete_organizer(request, organizer_id):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    organizer = get_object_or_404(ElectionOrganizer, id=organizer_id)
    user = organizer.user
    name = user.get_full_name()
    
    from .utils import log_action
    log_action(request.user, f"Deleted Organizer: {user.email}", request)
    
    organizer.delete()
    user.delete()
    
    messages.success(request, f"Organizer account for {name} has been permanently deleted.")
    return redirect('list_organizers')

def toggle_system_otp(request):
    from .models import SystemConfig
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    config = SystemConfig.get_config()
    config.enable_otp_emails = not config.enable_otp_emails
    config.save()
    
    status = "enabled" if config.enable_otp_emails else "disabled"
    messages.info(request, f"System OTP emails have been {status}.")
    return redirect('grand_admin_dashboard')

def toggle_system_receipts(request):
    from .models import SystemConfig
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    config = SystemConfig.get_config()
    config.enable_receipt_emails = not config.enable_receipt_emails
    config.save()
    
    status = "enabled" if config.enable_receipt_emails else "disabled"
    messages.info(request, f"System voting receipts have been {status}.")
    return redirect('grand_admin_dashboard')

def manage_plan_pricing(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    from .models import PlanPricing
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        price = request.POST.get('price')
        limit = request.POST.get('limit')
        
        plan = get_object_or_404(PlanPricing, id=plan_id)
        plan.price_per_email = price
        plan.max_emails = limit
        plan.save()
        
        from .utils import log_action
        log_action(request.user, f"Updated pricing for {plan.plan_name}: {price}/email, limit {limit}", request)
        messages.success(request, f"Pricing updated for {plan.get_plan_name_display()} plan.")
        
    return redirect('grand_admin_dashboard')

def export_audit_pdf(request, short_id):
    from .models import Election, Voter
    from django.http import FileResponse
    from .analytics_pdf_utils import generate_election_audit_pdf
    
    election = get_object_or_404(Election, short_id=short_id)
    
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser or election.organizer.user == request.user):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if election.plan != 'PREMIUM':
        messages.error(request, "PDF Audit Reports are a Premium feature.")
        return redirect('election_analytics', short_id=election.short_id)
        
    voters = Voter.objects.filter(election=election).order_by('user__last_name')
    total_votes_cast = Voter.objects.filter(election=election, has_voted=True).count()
    
    buffer = generate_election_audit_pdf(election, voters, total_votes_cast)
    
    return FileResponse(buffer, as_attachment=True, filename=f'audit_report_{election.id}.pdf')

def list_all_elections(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')

    all_elections = Election.objects.all().order_by('-created_at')
    
    search_query = request.GET.get('q')
    if search_query:
        all_elections = all_elections.filter(
            models.Q(title__icontains=search_query) |
            models.Q(institution__name__icontains=search_query) |
            models.Q(organizer__user__email__icontains=search_query)
        )

    paginator = Paginator(all_elections, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'election_core/admin_elections_list.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })

def list_all_payments(request):
    if not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')

    from .models import ElectionPayment
    all_payments = ElectionPayment.objects.filter(is_verified=True).order_by('-paid_at')
    
    search_query = request.GET.get('q')
    if search_query:
        all_payments = all_payments.filter(
            models.Q(election__title__icontains=search_query) |
            models.Q(election__organizer__user__email__icontains=search_query) |
            models.Q(reference__icontains=search_query)
        )

    paginator = Paginator(all_payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'election_core/admin_payments_list.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })
