import random
import string
from django.utils import timezone
from datetime import timedelta
import hmac
import hashlib
import uuid
from django.conf import settings
from .models import AuditLog, OTP

def generate_otp(user, purpose, expiry_minutes=5):
    OTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
    
    code = ''.join(random.choices(string.digits, k=6))
    expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
    
    otp_obj = OTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=expires_at
    )
    return code

def verify_otp(user, code, purpose):
    otp_obj = OTP.objects.filter(
        user=user, 
        code=code, 
        purpose=purpose, 
        is_used=False,
        expires_at__gt=timezone.now()
    ).first()
    
    if otp_obj:
        otp_obj.is_used = True
        otp_obj.save()
        return True, "OTP verified successfully."
    
    return False, "Invalid or expired OTP."

def log_action(user, action, request=None, extra_data=None):
    ip_address = None
    user_agent = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT')
        
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        ip_address=ip_address,
        device_info=user_agent,
        extra_data=extra_data
    )

def sign_vote(election_id, position_id, candidate_id):
    data = f"{election_id}:{position_id}:{candidate_id}"
    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def generate_verification_id():
    return uuid.uuid4().hex[:12].upper()

def is_rate_limited(request, action, limit=5, window_minutes=10):
    from django.utils import timezone
    from datetime import timedelta
    
    since = timezone.now() - timedelta(minutes=window_minutes)
    
    if request.user.is_authenticated:
        count = AuditLog.objects.filter(
            user=request.user,
            action=action,
            timestamp__gt=since
        ).count()
    else:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
            
        count = AuditLog.objects.filter(
            ip_address=ip_address,
            action=action,
            timestamp__gt=since
        ).count()
        
    return count >= limit
