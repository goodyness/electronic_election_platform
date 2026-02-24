from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from .models import ElectionOrganizer, OTP, Institution, AllowedEmail, Voter
from .utils import generate_otp

User = get_user_model()

def register_organizer(first_name, last_name, email, contact, institution_id, password):
    """
    Registers a new Election Organizer.
    Creates a User and an ElectionOrganizer profile.
    Triggers OTP for email verification.
    """
    with transaction.atomic():
        institution = Institution.objects.get(id=institution_id)
        
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='ORGANIZER',
            institution=institution,
            contact=contact,
            is_active=False # Inactive until OTP verification
        )
        
        organizer = ElectionOrganizer.objects.create(
            user=user,
            status='PENDING_APPROVAL'
        )
        
        # Generate OTP
        otp_code = generate_otp(user, 'ORGANIZER_VERIFICATION')
        
        # Send Email via Celery
        from .tasks import send_otp_email_task
        send_otp_email_task.delay(email, otp_code, 'ORGANIZER_VERIFICATION')
        
        return user, organizer

def register_voter(full_name, email, matric_number, faculty, department, institution_id, election_id, password, skip_otp=False):
    """
    Registers a new Voter for a specific election.
    Reuses an existing User if one exists with this email (for multi-election support).
    Checks if email is in AllowedEmail list.
    Enforces institution matching with the election organizer's institution.
    """
    from .models import Election
    with transaction.atomic():
        election = Election.objects.get(id=election_id)
        institution = Institution.objects.get(id=institution_id)
        
        # Institution matching: voter's school must match election's institution
        if institution.id != election.institution_id:
            raise Exception(f"You must belong to {election.institution.name} to participate in this election.")
        
        # Check if email is allowed
        if not AllowedEmail.objects.filter(election_id=election_id, email=email).exists():
            raise Exception("Your email is not on the allowed list for this election.")
        
        # Check if already accredited for THIS election (by email)
        if Voter.objects.filter(user__email=email, election_id=election_id).exists():
            raise Exception("You are already accredited for this election.")
        
        # Check matric number uniqueness for this election
        if Voter.objects.filter(election_id=election_id, matric_number=matric_number).exists():
            raise Exception("A voter with this matric number is already registered for this election.")

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Reuse existing user or create new one
        try:
            user = User.objects.get(email=email)
            # User already exists — reuse for this new election
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='VOTER',
                institution=institution,
                is_active=True if skip_otp else False
            )
        
        voter = Voter.objects.create(
            user=user,
            election_id=election_id,
            matric_number=matric_number,
            faculty=faculty,
            department=department,
            is_accredited=True if skip_otp else False
        )
        
        if not skip_otp:
            # OTP for accreditation
            otp_code = generate_otp(user, 'VOTER_ACCREDITATION')
            
            # Send Email via Celery
            from .tasks import send_otp_email_task
            send_otp_email_task.delay(email, otp_code, 'VOTER_ACCREDITATION')
        
        return user, voter

def verify_voter_accreditation(user, code):
    """
    Verifies voter OTP and marks them as accredited.
    Finds the most recent unaccredited voter profile for this user.
    """
    from .utils import verify_otp
    success, message = verify_otp(user, code, 'VOTER_ACCREDITATION')
    if success:
        user.is_active = True
        user.save()
        # Find the latest unaccredited voter profile
        voter = Voter.objects.filter(user=user, is_accredited=False).order_by('-id').first()
        if voter:
            voter.is_accredited = True
            voter.save()
            return True, "Accreditation successful. You can now login to vote when the election is active."
        return False, "No pending accreditation found."
    return False, message

def verify_organizer_email(user, code):
    """
    Verifies the email of an organizer and marks user as active.
    Wait for Admin approval for the organizer profile separately.
    """
    from .utils import verify_otp
    success, message = verify_otp(user, code, 'ORGANIZER_VERIFICATION')
    if success:
        user.is_active = True
        user.save()
        return True, "Email verified successfully. Your account is now pending admin approval."
    return False, message

def initiate_password_reset(email):
    """
    Initiates a password reset by sending an OTP.
    """
    try:
        user = User.objects.get(email=email)
        otp_code = generate_otp(user, 'PASSWORD_RESET')
        
        from .tasks import send_otp_email_task
        send_otp_email_task.delay(email, otp_code, 'PASSWORD_RESET')
        return True, "Reset code sent to your email."
    except User.DoesNotExist:
        # For security, we might still say "check email" but for internal logic, 
        # let's be descriptive for now or handle appropriately in view.
        return False, "User with this email does not exist."

def complete_password_reset(email, code, new_password):
    """
    Completes password reset using OTP verification.
    """
    try:
        user = User.objects.get(email=email)
        from .utils import verify_otp
        success, message = verify_otp(user, code, 'PASSWORD_RESET')
        if success:
            user.set_password(new_password)
            user.is_active = True # Ensure they can login if they were inactive
            user.save()
            return True, "Password reset successful. You can now login."
        return False, message
    except User.DoesNotExist:
        return False, "User not found."

