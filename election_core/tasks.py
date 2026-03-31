from celery import shared_task
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from .models import SystemConfig, Election
import csv
import io
import os

@shared_task
def send_otp_email_task(email, otp_code, purpose):
    config = SystemConfig.get_config()
    if not config.enable_otp_emails:
        return "OTP Emails disabled globally."

    if purpose == 'ORGANIZER_VERIFICATION':
        purpose_text = 'Account Verification'
    elif purpose == 'PASSWORD_RESET':
        purpose_text = 'Password Reset'
    else:
        purpose_text = 'Vote Accreditation'
    subject = f'Election System: {purpose_text} Code'
    
    context = {
        'subject': subject,
        'purpose_text': purpose_text,
        'otp_code': otp_code,
        'current_year': timezone.now().year,
    }
    
    html_content = render_to_string('emails/otp_email.html', context)
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
        [email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return f"OTP Email sent to {email}"

@shared_task
def send_verification_receipt_task(email, election_title, receipt_id, election_id):
    config = SystemConfig.get_config()
    if not config.enable_receipt_emails:
        return "Receipt Emails disabled globally."
    
    try:
        election = Election.objects.get(id=election_id)
        if not election.send_receipts:
            return f"Receipts disabled for election {election_id}"
    except Election.DoesNotExist:
        return f"Election {election_id} not found."

    subject = f'Voting Receipt: {election_title}'
    context = {
        'election_title': election_title,
        'receipt_id': receipt_id,
        'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'current_year': timezone.now().year,
    }
    
    html_content = render_to_string('emails/receipt_email.html', context)
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
        [email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return f"Receipt sent to {email}"

@shared_task
def process_bulk_voter_upload_task(election_id, file_path, max_to_add=None):
    from .models import Election, AllowedEmail
    
    try:
        election = Election.objects.get(id=election_id)
        count = 0
        errors = 0
        limit_reached = False
        
        emails_to_add = set()
        existing_emails = set(AllowedEmail.objects.filter(election=election).values_list('email', flat=True))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue
                
                email = row[0].strip()
                if email and '@' in email:
                    if email not in existing_emails and email not in emails_to_add:
                        if max_to_add is not None and len(emails_to_add) >= max_to_add:
                            limit_reached = True
                            break
                        emails_to_add.add(email)
                    else:
                        errors += 1
                        
        if emails_to_add:
            objs = [AllowedEmail(election=election, email=e) for e in emails_to_add]
            AllowedEmail.objects.bulk_create(objs, ignore_conflicts=True)
            count = len(objs)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        msg = f"Processed {count} new emails."
        if errors:
            msg += f" {errors} duplicates/errors skipped."
        if limit_reached:
            msg += f" STOPPED at {max_to_add} (Plan limit reached)."
            
        return msg
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return f"Error: {str(e)}"

@shared_task
def send_voter_nudge_task(email, election_title, site_url):
    subject = f'Reminder: Vote in {election_title}'
    
    context = {
        'election_title': election_title,
        'site_url': site_url,
        'current_year': timezone.now().year,
    }
    
    html_content = render_to_string('emails/nudge_email.html', context)
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
        [email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return f"Nudge sent to {email}"

@shared_task
def send_payment_receipt_task(email, user_name, election_title, plan_name, email_count, amount_str, dashboard_url):
    subject = f"Receipt for {election_title}"
    context = {
        'user_name': user_name,
        'election_title': election_title,
        'plan_name': plan_name,
        'email_count': email_count,
        'amount': amount_str,
        'dashboard_url': dashboard_url
    }
    
    html_message = render_to_string('election_core/emails/payment_success_email.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=True
    )
    return f"Payment receipt sent to {email}"

@shared_task
def send_organizer_approval_email_task(email, full_name, dashboard_url):
    subject = "FlashVote: Your Organizer Account is Approved!"
    context = {
        'full_name': full_name,
        'dashboard_url': dashboard_url,
        'current_year': timezone.now().year,
    }
    
    html_content = render_to_string('election_core/emails/organizer_approved_email.html', context)
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
        [email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return f"Approval email sent to {email}"

@shared_task
def notify_superadmin_election_created_task(election_id, dashboard_url):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    superadmins = User.objects.filter(is_superuser=True)
    if not superadmins.exists():
        return "No superadmin found."
    
    try:
        election = Election.objects.get(id=election_id)
    except Election.DoesNotExist:
        return "Election not found."
        
    if election.election_type == 'CONTESTANT':
        return f"Contest {election.id} auto-cleared, no notification sent."
        
    subject = f"Action Required: Clearance for {election.title}"
    context = {
        'election_title': election.title,
        'organizer_name': election.organizer.user.get_full_name(),
        'dashboard_url': dashboard_url,
        'current_year': timezone.now().year,
    }
    html_content = render_to_string('election_core/emails/clearance_request_email.html', context)
    text_content = strip_tags(html_content)
    
    for admin in superadmins:
        admin_email = getattr(settings, 'ADMIN_EMAIL', admin.email)
        if admin_email:
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL or 'noreply@election.com', [admin_email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
    return f"Clearance request emails sent for election {election.id}"

@shared_task
def send_batch_tokens_task(election_id, limit, login_url):
    from .models import Election, AllowedEmail, ElectionToken
    from django.core import mail
    try:
        election = Election.objects.get(id=election_id)
        # Find allowed emails without tokens for this election
        pending_emails = AllowedEmail.objects.filter(election=election).exclude(electiontoken__isnull=False)[:limit]
        
        if not pending_emails.exists():
            return "No pending tokens to send."

        # 1. Prepare and Bulk Create Tokens for speed
        tokens_to_create = []
        expires_at = timezone.now() + timezone.timedelta(hours=48)
        
        for allowed in pending_emails:
            tokens_to_create.append(ElectionToken(
                election=election,
                allowed_email=allowed,
                expires_at=expires_at
            ))
        
        created_tokens = ElectionToken.objects.bulk_create(tokens_to_create)
        
        # 2. Batch Send Emails using a single connection
        connection = mail.get_connection()
        messages = []
        
        for token in created_tokens:
            subject = f"Your Accreditation Token for {election.title}"
            context = {
                'election_title': election.title,
                'token': token.token,
                'login_url': login_url,
                'expires_at': token.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                'current_year': timezone.now().year,
            }
            html_content = render_to_string('election_core/emails/token_email.html', context)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject, 
                text_content, 
                settings.DEFAULT_FROM_EMAIL or 'noreply@election.com', 
                [token.allowed_email.email]
            )
            msg.attach_alternative(html_content, "text/html")
            messages.append(msg)
        
        # Send all messages in one go
        connection.send_messages(messages)
            
        election.last_token_send_time = timezone.now()
        election.save()
            
        return f"Sent {len(created_tokens)} tokens for election {election.id}"
    except Exception as e:
        return f"Error sending batch tokens: {str(e)}"

@shared_task
def send_single_token_task(token_id, login_url):
    from .models import ElectionToken
    try:
        token = ElectionToken.objects.get(id=token_id)
        election = token.election
        subject = f"Your Accreditation Token for {election.title}"
        context = {
            'election_title': election.title,
            'token': token.token,
            'login_url': login_url,
            'expires_at': token.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            'current_year': timezone.now().year,
        }
        html_content = render_to_string('election_core/emails/token_email.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
            [token.allowed_email.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return f"Token resend successful for {token.allowed_email.email}"
    except Exception as e:
        return f"Error resending token: {str(e)}"

@shared_task
def send_vote_receipt_task(vote_id):
    from .models import Vote
    try:
        vote = Vote.objects.get(id=vote_id)
        subject = f"Vote Confirmation: {vote.election.title}"
        context = {
            'voter_name': vote.voter_name,
            'election_title': vote.election.title,
            'candidate_name': vote.candidate.full_name,
            'amount': vote.amount_paid,
            'timestamp': vote.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'reference': vote.paystack_reference,
            'current_year': timezone.now().year,
        }
        
        html_content = render_to_string('election_core/emails/vote_receipt_email.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL or 'noreply@election.com',
            [vote.voter_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return f"Vote receipt sent to {vote.voter_email}"
    except Vote.DoesNotExist:
        return f"Vote {vote_id} not found."
    except Exception as e:
        return f"Error sending vote receipt: {str(e)}"

@shared_task
def send_withdrawal_request_notification_task(withdrawal_id):
    from .models import Withdrawal
    try:
        w = Withdrawal.objects.get(id=withdrawal_id)
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@flashvote.ng')
        organizer_email = w.wallet.user.email
        
        # 1. Email to Admin
        admin_subject = f"New Withdrawal Request: ₦{w.amount} from {organizer_email}"
        admin_context = {
            'withdrawal': w,
            'organizer_email': organizer_email,
            'admin_url': f"http://127.0.0.1:8000/admin/election_core/withdrawal/{w.id}/change/"
        }
        admin_html = render_to_string('election_core/emails/withdrawal_request_admin.html', admin_context)
        send_mail(admin_subject, strip_tags(admin_html), settings.DEFAULT_FROM_EMAIL, [admin_email], html_message=admin_html)
        
        # 2. Email to Organizer (Confirmation)
        org_subject = f"Withdrawal Request Received: ₦{w.amount}"
        org_context = {
            'withdrawal': w,
            'full_name': w.wallet.user.get_full_name()
        }
        org_html = render_to_string('election_core/emails/withdrawal_request_organizer.html', org_context)
        send_mail(org_subject, strip_tags(org_html), settings.DEFAULT_FROM_EMAIL, [organizer_email], html_message=org_html)
        
        return f"Withdrawal notifications sent for request {withdrawal_id}"
    except Exception as e:
        return f"Error sending withdrawal notification: {str(e)}"

@shared_task
def send_withdrawal_status_notification_task(withdrawal_id):
    from .models import Withdrawal
    try:
        w = Withdrawal.objects.get(id=withdrawal_id)
        organizer_email = w.wallet.user.email
        subject = f"Withdrawal Request {w.status}: ₦{w.amount}"
        context = {
            'withdrawal': w,
            'full_name': w.wallet.user.get_full_name()
        }
        html_content = render_to_string('election_core/emails/withdrawal_status_update.html', context)
        send_mail(subject, strip_tags(html_content), settings.DEFAULT_FROM_EMAIL, [organizer_email], html_message=html_content)
        return f"Status update sent to {organizer_email} for withdrawal {withdrawal_id}"
    except Exception as e:
        return f"Error: {str(e)}"
