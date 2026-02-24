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
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue
                
                if max_to_add is not None and count >= max_to_add:
                    limit_reached = True
                    break
                    
                email = row[0].strip()
                if email and '@' in email:
                    try:
                        _, created = AllowedEmail.objects.get_or_create(election=election, email=email)
                        if created:
                            count += 1
                        else:
                            errors += 1
                    except:
                        errors += 1
        
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
def send_voter_nudge_task(email, election_title):
    subject = f'Reminder: Vote in {election_title}'
    
    context = {
        'election_title': election_title,
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
