import csv
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from .forms import OrganizerRegistrationForm, OTPVerificationForm, LoginForm, VoterAccreditationForm, VoterDetailsForm, ForgotPasswordForm, PasswordResetForm
from .services import register_organizer, verify_organizer_email, initiate_password_reset, complete_password_reset
from .models import User, OTP, Institution, Election, Position, Candidate, Voter, AuditLog, Vote, ElectionOrganizer

User = get_user_model()

def home(request):
    from .models import Election
    active_elections = Election.objects.filter(status='ACTIVE').order_by('-start_time')
    return render(request, 'election_core/home.html', {'elections': active_elections})

def active_elections_list(request):
    from .models import Election
    active_elections = Election.objects.filter(status='ACTIVE').order_by('-start_time')
    return render(request, 'election_core/active_elections.html', {'elections': active_elections})


def organizer_signup(request):
    if request.method == 'POST':
        form = OrganizerRegistrationForm(request.POST)
        if form.is_valid():
            try:
                register_organizer(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    email=form.cleaned_data['email'],
                    contact=form.cleaned_data['contact'],
                    institution_id=form.cleaned_data['institution'].id,
                    password=form.cleaned_data['password']
                )
                from .utils import log_action
                log_action(None, f"Organizer Signup: {form.cleaned_data['email']}", request)
                messages.success(request, "Registration successful. Please check your email for the verification OTP.")
                return redirect('verify_otp', email=form.cleaned_data['email'])
            except Exception as e:
                messages.error(request, f"Error during registration: {str(e)}")
    else:
        form = OrganizerRegistrationForm()
    return render(request, 'election_core/organizer_signup.html', {'form': form})

def voter_accreditation(request, short_id):
    from .models import Election, Voter
    election = get_object_or_404(Election, short_id=short_id)
    
    if request.user.is_authenticated:
        voter = Voter.objects.filter(user=request.user, election=election).first()
        if voter:
            if voter.has_voted:
                messages.info(request, "You have already cast your vote for this election.")
                return redirect('voter_dashboard')
            return redirect('cast_vote', short_id=election.short_id)

    if request.method == 'POST':
        from .utils import is_rate_limited, log_action
        if is_rate_limited(request, "VOTER_ACCREDITATION_REQUEST", limit=5, window_minutes=10):
            messages.error(request, "Too many accreditation attempts. Please try again later.")
            return redirect('home')
        
        form = VoterAccreditationForm(request.POST)
        details_form = VoterDetailsForm(request.POST)
        if form.is_valid() and details_form.is_valid():
            email = form.cleaned_data['email']
            existing_user = User.objects.filter(email=email).first()
            log_action(existing_user, "VOTER_ACCREDITATION_REQUEST", request, extra_data={'email': email})

            try:
                from .services import register_voter
                skip_otp = (election.plan == 'FREE')
                
                password = form.cleaned_data.get('password')
                
                register_voter(
                    full_name=f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}",
                    email=email,
                    matric_number=details_form.cleaned_data['matric_number'],
                    faculty=details_form.cleaned_data['faculty'],
                    department=details_form.cleaned_data['department'],
                    institution_id=form.cleaned_data['institution'].id,
                    election_id=election.id,
                    password=password,
                    skip_otp=skip_otp
                )
                if skip_otp:
                    messages.success(request, "Accreditation successful! You can now login to vote.")
                    return redirect('login')
                else:
                    messages.success(request, "Accreditation started. Please check your email for OTP.")
                    return redirect('verify_otp', email=form.cleaned_data['email'])
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = VoterAccreditationForm()
        details_form = VoterDetailsForm()
    return render(request, 'election_core/voter_accreditation.html', {
        'form': form, 
        'details_form': details_form,
        'election': election
    })

def verify_otp(request, email):
    user = get_object_or_404(User, email=email)
    if request.method == 'POST':
        from .utils import is_rate_limited, log_action
        if is_rate_limited(request, "OTP_VERIFICATION_ATTEMPT", limit=5, window_minutes=5):
            messages.error(request, "Too many failed attempts. Please try again in 5 minutes.")
            return redirect('home')
            
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            log_action(user, "OTP_VERIFICATION_ATTEMPT", request)
            code = form.cleaned_data['otp_code']
            
            if user.role == 'ORGANIZER':
                from .services import verify_organizer_email
                success, message = verify_organizer_email(user, code)
            else:
                from .services import verify_voter_accreditation
                success, message = verify_voter_accreditation(user, code)
                
            if success:
                messages.success(request, message)
                return redirect('login')
            else:
                messages.error(request, message)
    else:
        form = OTPVerificationForm(initial={'email': email})
    return render(request, 'election_core/verify_otp.html', {'form': form, 'email': email})

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            success, message = initiate_password_reset(email)
            if success:
                messages.success(request, message)
                return redirect('reset_password', email=email)
            else:
                messages.error(request, message)
    else:
        form = ForgotPasswordForm()
    return render(request, 'election_core/forgot_password.html', {'form': form})

def reset_password(request, email):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            success, message = complete_password_reset(
                email=form.cleaned_data['email'],
                code=form.cleaned_data['otp_code'],
                new_password=form.cleaned_data['new_password']
            )
            if success:
                messages.success(request, message)
                return redirect('login')
            else:
                messages.error(request, message)
    else:
        form = PasswordResetForm(initial={'email': email})
    return render(request, 'election_core/reset_password.html', {'form': form, 'email': email})

def check_user_exists(request):
    email = request.GET.get('email', '').strip()
    if not email:
        return JsonResponse({'exists': False})
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})

def resend_otp(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            user = User.objects.get(email=email)
            purpose = 'VOTER_ACCREDITATION' if user.role == 'VOTER' else 'ORGANIZER_VERIFICATION'
            
            from .utils import generate_otp
            otp_code = generate_otp(user, purpose)
            
            from .tasks import send_otp_email_task
            send_otp_email_task.delay(email, otp_code, purpose)
            
            return JsonResponse({'success': True, 'message': 'New OTP sent to your email.'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request.'})

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user:
                if user.is_active:
                    login(request, user)
                    from .utils import log_action
                    log_action(user, "User Login", request)
                    if user.role == 'ORGANIZER':
                        return redirect('organizer_dashboard')
                    elif user.role == 'VOTER':
                        return redirect('voter_dashboard')
                    elif user.role == 'GRAND_ADMIN' or user.is_superuser:
                        return redirect('grand_admin_dashboard')
                    else:
                        return redirect('admin:index')
                else:
                    messages.error(request, "Account is not active. Please verify your email first.")
            else:
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, 'election_core/login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('home')

def organizer_dashboard(request):
    from .models import Election, ElectionOrganizer
    if request.user.role != 'ORGANIZER' and not request.user.is_superuser:
        messages.error(request, "Access denied. This dashboard is for Organizers only.")
        return redirect('home')
        
    try:
        organizer = ElectionOrganizer.objects.get(user=request.user)
    except ElectionOrganizer.DoesNotExist:
        if request.user.is_superuser:
            messages.info(request, "Superuser dashboard view. No organizer profile found.")
            elections = Election.objects.all()
            return render(request, 'election_core/organizer_dashboard.html', {
                'elections': elections,
                'organizer': None
            })
        messages.error(request, "Organizer profile not found.")
        return redirect('home')
        
    elections = Election.objects.filter(organizer=organizer)
    from .models import ElectionPayment
    payment_history = ElectionPayment.objects.filter(election__organizer=organizer, is_verified=True).order_by('-paid_at')
    
    return render(request, 'election_core/organizer_dashboard.html', {
        'elections': elections,
        'organizer': organizer,
        'payment_history': payment_history
    })

def view_election_results(request, short_id):
    from .models import Election, Position, Vote, AllowedEmail
    from django.db.models import Count
    
    election = get_object_or_404(Election, short_id=short_id)
    
    is_organizer = (request.user.role == 'ORGANIZER' and election.organizer.user == request.user)
    is_admin = (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser)
    is_voter = (request.user.role == 'VOTER' and election.status == 'CLOSED')
    
    if not (is_admin or is_organizer or is_voter):
        messages.error(request, "Results are not yet public.")
        return redirect('home')

    accredited_count = Voter.objects.filter(election=election, is_accredited=True).count()
    voted_count = Voter.objects.filter(election=election, has_voted=True).count()
    eligible_count = AllowedEmail.objects.filter(election=election).count()

    results = []
    positions = election.positions.all()
    for position in positions:
        candidates = position.candidates.annotate(vote_count=Count('vote')).order_by('-vote_count')
        position_total = sum(c.vote_count for c in candidates)
        results.append({
            'position': position,
            'candidates': candidates,
            'total_votes': position_total
        })
        
    return render(request, 'election_core/election_results.html', {
        'election': election,
        'results': results,
        'accredited_count': accredited_count,
        'voted_count': voted_count,
        'eligible_count': eligible_count
    })

from django.contrib.auth.decorators import login_required

@login_required
def voter_dashboard(request):
    if request.user.role != 'VOTER':
        messages.error(request, "Access denied. This dashboard is for Voters only.")
        return redirect('home')
    from .models import Election, Voter
    voter_profiles = Voter.objects.filter(user=request.user, is_accredited=True)
    elections = [vp.election for vp in voter_profiles]
    return render(request, 'election_core/voter_dashboard.html', {'elections': elections})

def cast_vote_view(request, short_id):
    from .models import Election, Position, Voter
    from .voting_logic import cast_vote
    
    election = get_object_or_404(Election, short_id=short_id)
    voter = get_object_or_404(Voter, user=request.user, election=election)
    
    if not voter.is_accredited:
        messages.error(request, "You are not accredited for this election.")
        return redirect('voter_dashboard')
        
    if voter.has_voted:
        messages.warning(request, "You have already cast your vote.")
        return redirect('voter_dashboard')

    positions = election.positions.all().prefetch_related('candidates')
    
    if request.method == 'POST':
        from .utils import is_rate_limited, log_action
        if is_rate_limited(request, "VOTE_CAST_ATTEMPT", limit=3, window_minutes=5):
            messages.error(request, "System busy. Please wait a few minutes before trying to vote again.")
            return redirect('voter_dashboard')
            
        votes_data = []
        try:
            for position in positions:
                candidate_id = request.POST.get(f'position_{position.id}')
                if not candidate_id:
                    raise Exception(f"Please select a candidate for {position.title}")
                votes_data.append({
                    'position_id': position.id,
                    'candidate_id': int(candidate_id)
                })
            
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')

            success, message = cast_vote(request.user, election.id, votes_data, ip_address=ip_address, user_agent=user_agent)
            if success:
                from .utils import log_action
                log_action(request.user, f"Cast Vote in Election {election.id}", request)
                messages.success(request, message)
                return redirect('voter_dashboard')
        except Exception as e:
            messages.error(request, str(e))
            
    return render(request, 'election_core/cast_vote.html', {
        'election': election,
        'positions': positions
    })

def create_election(request):
    from .models import ElectionOrganizer
    if not (request.user.role == 'ORGANIZER' or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    organizer = get_object_or_404(ElectionOrganizer, user=request.user)
    if organizer.status != 'APPROVED' and not request.user.is_superuser:
        messages.error(request, "Your account must be approved before you can create elections.")
        return redirect('organizer_dashboard')
        
    if request.method == 'POST':
        from .forms import ElectionForm
        form = ElectionForm(request.POST)
        if form.is_valid():
            election = form.save(commit=False)
            election.institution = organizer.user.institution
            election.organizer = organizer
            election.save()
            messages.success(request, f"Election '{election.title}' created! Please select a plan to proceed.")
            return redirect('select_plan', short_id=election.short_id)
    else:
        from .forms import ElectionForm
        form = ElectionForm()
        
    return render(request, 'election_core/create_election.html', {'form': form})

def manage_election(request, short_id):
    from .models import Election
    election = get_object_or_404(Election, short_id=short_id)
    
    if election.organizer.user != request.user:
        if request.user.role == 'GRAND_ADMIN' or request.user.is_superuser:
            return redirect('election_analytics', short_id=election.short_id)
        messages.error(request, "Access denied.")
        return redirect('home')
        
    positions = election.positions.all().prefetch_related('candidates')
    
    from .payment_views import election_is_paid
    is_paid = election_is_paid(election)
    
    if request.method == 'POST' and 'update_slug' in request.POST:
        if election.plan != 'PREMIUM':
            messages.error(request, "Custom URLs are a Premium feature.")
        else:
            new_slug = request.POST.get('custom_slug', '').strip().lower()
            if new_slug:
                from django.utils.text import slugify
                safe_slug = slugify(new_slug)
                if Election.objects.filter(custom_slug=safe_slug).exclude(id=election.id).exists():
                    messages.error(request, "This custom URL is already taken.")
                else:
                    election.custom_slug = safe_slug
                    election.save()
                    messages.success(request, f"Custom URL updated: /e/{safe_slug}/")
            else:
                election.custom_slug = None
                election.save()
                messages.success(request, "Custom URL removed.")
        return redirect('manage_election', short_id=election.short_id)
        
    if request.method == 'POST' and 'update_branding' in request.POST:
        if election.plan == 'FREE':
            messages.error(request, "Branding and themes are available on Standard/Premium plans.")
        else:
            if 'logo' in request.FILES:
                election.logo = request.FILES['logo']
            
            if election.plan == 'PREMIUM':
                new_theme = request.POST.get('theme', 'default')
                election.theme = new_theme
            
            election.save()
            messages.success(request, "Branding settings updated.")
        return redirect('manage_election', short_id=election.short_id)
    
    return render(request, 'election_core/manage_election.html', {
        'election': election,
        'positions': positions,
        'is_paid': is_paid
    })

def add_position(request, short_id):
    from .models import Election
    election = get_object_or_404(Election, short_id=short_id)
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    from .payment_views import election_is_paid
    if not election_is_paid(election):
        messages.warning(request, "Please select and complete payment for a plan to add positions.")
        return redirect('select_plan', short_id=election.short_id)
        
    if request.method == 'POST':
        from .forms import PositionForm
        form = PositionForm(request.POST)
        if form.is_valid():
            position = form.save(commit=False)
            position.election = election
            position.save()
            return redirect('manage_election', short_id=election.short_id)
    else:
        from .forms import PositionForm
        form = PositionForm()
        
    return render(request, 'election_core/add_position.html', {'form': form, 'election': election})

def add_candidate(request, position_id):
    from .models import Position
    position = get_object_or_404(Position, id=position_id)
    election = position.election
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    from .payment_views import election_is_paid
    if not election_is_paid(election):
        messages.warning(request, "Please select and complete payment for a plan to add positions.")
        return redirect('select_plan', short_id=election.short_id)
        
    if request.method == 'POST':
        from .forms import CandidateForm
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.position = position
            candidate.save()
            return redirect('manage_election', short_id=election.short_id)
    else:
        from .forms import CandidateForm
        form = CandidateForm()
        
    return render(request, 'election_core/add_candidate.html', {
        'form': form, 
        'position': position,
        'election': election
    })

def edit_candidate(request, candidate_id):
    from .models import Candidate
    from .forms import CandidateForm
    candidate = get_object_or_404(Candidate, id=candidate_id)
    position = candidate.position
    election = position.election
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, instance=candidate)
        if form.is_valid():
            form.save()
            return redirect('manage_election', short_id=election.short_id)
    else:
        form = CandidateForm(instance=candidate)
        
    return render(request, 'election_core/add_candidate.html', {
        'form': form, 
        'position': position,
        'election': election,
        'is_edit': True
    })

def delete_candidate(request, candidate_id):
    from .models import Candidate
    candidate = get_object_or_404(Candidate, id=candidate_id)
    election = candidate.position.election
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    name = candidate.full_name
    candidate.delete()
    return redirect('manage_election', short_id=election.short_id)

def update_status(request, short_id, action):
    from .models import Election
    election = get_object_or_404(Election, short_id=short_id)
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if action == 'activate':
        if not election.positions.exists():
            messages.error(request, "Election must have at least one position before going live.")
        else:
            election.status = 'ACTIVE'
            election.save()
            messages.success(request, f"Election '{election.title}' is now LIVE!")
    elif action == 'freeze':
        election.status = 'FROZEN'
        election.save()
        messages.info(request, "Election frozen.")
    elif action == 'close':
        election.status = 'CLOSED'
        election.save()
        
        from django.db.models import Count
        
        election_voters = Voter.objects.filter(election=election)
        
        count = 0
        for voter in election_voters:
            user = voter.user
            other_profiles = Voter.objects.filter(user=user).exclude(election=election).exists()
            
            if not other_profiles:
                if user.role == 'VOTER':
                    user.delete()
                    count += 1
                
        messages.info(request, f"Election closed. {count} temporary voter accounts cleaned up.")
        
    return redirect('manage_election', short_id=election.short_id)

def toggle_voting(request, short_id):
    from .models import Election
    election = get_object_or_404(Election, short_id=short_id)
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
    
    election.is_voting_enabled = not election.is_voting_enabled
    election.save()
    
    status = "enabled" if election.is_voting_enabled else "disabled"
    messages.info(request, f"Voting has been {status} for this election.")
    return redirect('manage_election', short_id=election.short_id)

def toggle_election_receipts(request, short_id):
    from .models import Election
    election = get_object_or_404(Election, short_id=short_id)
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
    election.send_receipts = not election.send_receipts
    election.save()
    status = "enabled" if election.send_receipts else "disabled"
    messages.info(request, f"Email receipts have been {status} for this election.")
    return redirect('manage_election', short_id=election.short_id)

def extend_election_time(request, short_id):
    from .models import Election
    from datetime import timedelta
    election = get_object_or_404(Election, short_id=short_id)
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if request.method == 'POST':
        try:
            duration = int(request.POST.get('duration', 0))
            unit = request.POST.get('unit', 'hours')
            
            if duration > 0:
                if unit == 'minutes':
                    election.end_time += timedelta(minutes=duration)
                else:
                    election.end_time += timedelta(hours=duration)
                election.save()
                messages.success(request, f"Election extended by {duration} {unit}. New end time: {election.end_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                messages.error(request, "Invalid extension duration.")
        except ValueError:
            messages.error(request, "Please enter a valid number for duration.")
            
    return redirect('manage_election', short_id=election.short_id)

def manage_voter_list(request, short_id):
    import csv
    import io
    from .models import Election, AllowedEmail
    from .forms import AllowedEmailForm, BulkUploadForm
    election = get_object_or_404(Election, short_id=short_id)
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    allowed_emails = AllowedEmail.objects.filter(election=election).order_by('email')
    
    from .payment_views import get_email_limit
    limit = get_email_limit(election)
    current_count = allowed_emails.count()
    
    if request.method == 'POST':
        if 'email' in request.POST:
            if limit > 0 and current_count >= limit:
                messages.error(request, f"Email limit reached for your {election.get_plan_display()} plan ({limit} max). Please upgrade to add more.")
                return redirect('manage_voter_list', short_id=election.short_id)
                
            form = AllowedEmailForm(request.POST)
            bulk_form = BulkUploadForm()
            if form.is_valid():
                allowed_email = form.save(commit=False)
                allowed_email.election = election
                try:
                    allowed_email.save()
                    messages.success(request, f"Email {allowed_email.email} added.")
                except:
                    messages.error(request, "This email is already in the list.")
                return redirect('manage_voter_list', short_id=election.short_id)
        elif 'csv_file' in request.FILES:
            if limit > 0 and current_count >= limit:
                messages.error(request, f"Email limit reached for your {election.get_plan_display()} plan ({limit} max). Please upgrade to add more.")
                return redirect('manage_voter_list', short_id=election.short_id)
                
            bulk_form = BulkUploadForm(request.POST, request.FILES)
            form = AllowedEmailForm()
            if bulk_form.is_valid():
                csv_file = request.FILES['csv_file']
                try:
                    import tempfile
                    import os
                    from .tasks import process_bulk_voter_upload_task
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                        for chunk in csv_file.chunks():
                            tmp_file.write(chunk)
                        tmp_path = tmp_file.name
                    
                    remaining_slots = limit - current_count if limit > 0 else None
                    process_bulk_voter_upload_task.delay(election.id, tmp_path, max_to_add=remaining_slots)
                    
                    if remaining_slots is not None:
                        messages.success(request, f"Bulk upload started. Only the first {remaining_slots} valid emails will be added as per your {election.get_plan_display()} plan limits.")
                    else:
                        messages.success(request, "Bulk upload started in the background. It will be processed shortly.")
                except Exception as e:
                    messages.error(request, f"Error starting background process: {str(e)}")
                return redirect('manage_voter_list', short_id=election.short_id)
    else:
        form = AllowedEmailForm()
        bulk_form = BulkUploadForm()
        
    return render(request, 'election_core/manage_voter_list.html', {
        'election': election,
        'allowed_emails': allowed_emails,
        'form': form,
        'bulk_form': bulk_form,
        'limit': limit,
        'current_count': current_count,
        'remaining_count': limit - current_count if limit > 0 else None
    })

def delete_allowed_email(request, email_id):
    from .models import AllowedEmail
    allowed_email = get_object_or_404(AllowedEmail, id=email_id)
    election = allowed_email.election
    
    if not (election.organizer.user == request.user or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    email_str = allowed_email.email
    allowed_email.delete()
    messages.success(request, f"Email {email_str} removed from the list.")
    return redirect('manage_voter_list', short_id=election.short_id)

def export_results_csv(request, short_id):
    from django.shortcuts import get_object_or_404
    from .models import Election, Vote
    
    election = get_object_or_404(Election, short_id=short_id)
    
    is_organizer = (request.user.role == 'ORGANIZER' and election.organizer.user == request.user)
    is_admin = (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser)
    
    if not (is_organizer or is_admin):
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if election.plan == 'FREE' and not is_admin:
        messages.warning(request, "Result export is not available on the Free plan. Please upgrade to Basic or higher.")
        return redirect('election_results', short_id=election.short_id)
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{election.title}_results.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Position', 'Candidate', 'Verification ID', 'Digital Signature', 'IP Address'])
    
    votes = Vote.objects.filter(election=election).select_related('position', 'candidate').order_by('timestamp')
    
    for vote in votes:
        writer.writerow([
            vote.timestamp,
            vote.position.title,
            vote.candidate.full_name,
            vote.verification_id,
            vote.signature,
            vote.ip_address
        ])
        
    return response

def export_results_pdf(request, short_id):
    from .models import Election, Position, Candidate
    from django.db.models import Count
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from io import BytesIO
    
    election = get_object_or_404(Election, short_id=short_id)
    is_admin = (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser)
    is_organizer = (election.organizer.user == request.user)
    
    if not (is_admin or is_organizer):
        messages.error(request, "Access denied.")
        return redirect('home')

    if election.plan == 'FREE' and not is_admin:
        messages.warning(request, "Result export is not available on the Free plan. Please upgrade to Basic or higher.")
        return redirect('election_results', short_id=election.short_id)

    accredited_count = Voter.objects.filter(election=election, is_accredited=True).count()
    voted_count = Voter.objects.filter(election=election, has_voted=True).count()
    from .models import AllowedEmail
    eligible_count = AllowedEmail.objects.filter(election=election).count()
    total_participation_rate = (voted_count / accredited_count * 100) if accredited_count > 0 else 0

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=50)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = styles['Heading1']
    title_style.alignment = 1 
    
    elements.append(Paragraph(f"<b>{election.institution.name.upper()}</b>", title_style))
    elements.append(Paragraph(f"OFFICIAL ELECTION RESULT SHEET", styles['Heading2']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Election:</b> {election.title}", styles['Normal']))
    elements.append(Paragraph(f"<b>Status:</b> {election.get_status_display()}", styles['Normal']))
    elements.append(Paragraph(f"<b>Eligible Voters:</b> {eligible_count}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total Accredited:</b> {accredited_count}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total Voted:</b> {voted_count} ({total_participation_rate:.1f}%)", styles['Normal']))
    elements.append(Paragraph(f"<b>Reporting Date:</b> {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 24))
    
    positions = election.positions.all()
    for position in positions:
        elements.append(Paragraph(f"CATEGORY: {position.title.upper()}", styles['Heading3']))
        elements.append(Spacer(1, 6))
        
        candidates = position.candidates.annotate(vote_count=Count('vote')).order_by('-vote_count')
        
        max_votes = 0
        winners = []
        if candidates:
            max_votes = candidates[0].vote_count
            if max_votes > 0:
                winners = [c for c in candidates if c.vote_count == max_votes]
            
            data = [["Candidate Name", "Votes", "Status"]]
            for c in candidates:
                status = ""
                if max_votes > 0 and c.vote_count == max_votes:
                    status = "WINNER" if len(winners) == 1 else "TIE"
                data.append([c.full_name, c.vote_count, status])
            
            t = Table(data, colWidths=[300, 80, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            for i, c in enumerate(candidates):
                if max_votes > 0 and c.vote_count == max_votes:
                    row_color = colors.lightgreen if len(winners) == 1 else colors.lightyellow
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, i+1), (-1, i+1), row_color),
                    ]))
            
            elements.append(t)
            elements.append(Spacer(1, 12))
            
            if len(winners) == 1:
                declaration = f"<b>Declared Winner:</b> {winners[0].full_name}"
                elements.append(Paragraph(declaration, styles['Normal']))
            elif len(winners) > 1:
                elements.append(Paragraph("<b>Status:</b> Result is a TIE.", styles['Normal']))
            else:
                elements.append(Paragraph("<b>Status:</b> No valid votes cast for this position.", styles['Normal']))
        else:
            elements.append(Paragraph("No candidates found for this position.", styles['Normal']))
            
        elements.append(Spacer(1, 30))

    elements.append(Spacer(1, 50))
    sig_data = [
        ["..........................................", ".........................................."],
        ["Organizer Signature", "Date"],
        ["", ""],
        ["..........................................", ""],
        ["Grand Admin Verification", ""]
    ]
    sig_table = Table(sig_data, colWidths=[250, 250])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="E-Election_Results_{election.id}.pdf"'
    response.write(pdf)
    return response

def ballot_verification(request):
    from .models import Vote
    result = None
    v_id = request.GET.get('v_id')
    if v_id:
        result = Vote.objects.filter(verification_id=v_id).first()
        if not result:
            messages.error(request, "Invalid Verification ID.")
            
    return render(request, 'election_core/ballot_verification.html', {'result': result, 'v_id': v_id})

def nudge_voters(request, short_id):
    from .models import Election, Voter
    election = get_object_or_404(Election, short_id=short_id)
    
    if not (request.user.role == 'ORGANIZER' and election.organizer.user == request.user) and not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    if election.plan not in ['STANDARD', 'PREMIUM']:
        messages.error(request, "Voter Nudges are available on Standard and Premium plans only.")
        return redirect('election_analytics', short_id=election.short_id)
        
    pending_voters = Voter.objects.filter(election=election, is_accredited=True, has_voted=False)
    
    v_email = request.GET.get('v_email')
    if v_email:
        from .tasks import send_voter_nudge_task
        send_voter_nudge_task.delay(v_email, election.title)
        messages.success(request, f"Reminder sent to {v_email}.")
    else:
        from .tasks import send_voter_nudge_task
        for voter in pending_voters:
            send_voter_nudge_task.delay(voter.user.email, election.title)
        messages.success(request, f"Reminders are being sent to {pending_voters.count()} voters.")
        
    return redirect('election_analytics', short_id=election.short_id)

def result_war_room(request, short_id):
    from .models import Election, Position, Vote
    election = get_object_or_404(Election, short_id=short_id)
    
    if election.plan != 'PREMIUM' and not (request.user.role == 'GRAND_ADMIN' or request.user.is_superuser):
        messages.error(request, "Result War-Room is a Premium feature.")
        return redirect('election_results', short_id=election.short_id)
        
    positions = Position.objects.filter(election=election)
    results_data = []
    
    for pos in positions:
        candidates = pos.candidates.all()
        cand_results = []
        for cand in candidates:
            v_count = Vote.objects.filter(candidate=cand).count()
            cand_results.append({
                'name': cand.full_name,
                'votes': v_count,
                'photo': cand.photo.url if cand.photo else None,
                'aka': cand.aka
            })
        cand_results.sort(key=lambda x: x['votes'], reverse=True)
        results_data.append({
            'position': pos.title,
            'candidates': cand_results,
            'total_votes': sum(c['votes'] for c in cand_results)
        })
        
    context = {
        'election': election,
        'results_data': results_data,
        'refresh_interval': 10
    }
    
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'election_core/result_war_room_partial.html', context)
        
    return render(request, 'election_core/result_war_room.html', context)

def election_gateway(request, slug):
    from .models import Election, Voter
    election = get_object_or_404(Election, custom_slug=slug)
    
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
        
    voter = Voter.objects.filter(user=request.user, election=election).first()
    
    if not voter:
        return redirect('voter_accreditation', short_id=election.short_id)
    
    if voter.has_voted:
        messages.info(request, f"You have already participated in {election.title}.")
        return redirect('voter_dashboard')
        
    return redirect('cast_vote', short_id=election.short_id)
