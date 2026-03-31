from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class Institution(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (
        ('GRAND_ADMIN', 'Grand Admin'),
        ('ORGANIZER', 'Election Organizer'),
        ('VOTER', 'Voter'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, blank=True)
    contact = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class ElectionOrganizer(models.Model):
    STATUS_CHOICES = (
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organizer_profile')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_APPROVAL')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_organizers')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.status}"

class Election(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('FROZEN', 'Frozen'),
        ('CLOSED', 'Closed'),
    )
    PLAN_CHOICES = (
        ('FREE', 'Free'),
        ('BASIC', 'Basic'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
    )
    ACCREDITATION_CHOICES = (
        ('OTP', 'Email OTP'),
        ('TOKEN', 'Token-based'),
    )
    ELECTION_TYPE_CHOICES = (
        ('POLITICAL', 'Political Election'),
        ('CONTESTANT', 'Contestant Election'),
    )
    title = models.CharField(max_length=255)
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPE_CHOICES, default='POLITICAL')
    voting_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount organizer gets per vote (Contestant only)")
    description = models.TextField(null=True, blank=True, help_text="Description for Contestant Election")
    contest_image = models.ImageField(upload_to='contests/', null=True, blank=True, help_text="General image for Contestant Election")
    
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, null=True, blank=True)
    organizer = models.ForeignKey(ElectionOrganizer, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='FREE')
    custom_slug = models.SlugField(max_length=100, unique=True, null=True, blank=True, help_text="Custom URL slug for Premium plan")
    short_id = models.CharField(max_length=4, unique=True, null=True, blank=True, db_index=True)
    theme = models.CharField(max_length=50, default='default', help_text="UI Theme for Premium plan")
    logo = models.ImageField(upload_to='election_logos/', null=True, blank=True, help_text="Upload logo (Standard/Premium)")
    is_voting_enabled = models.BooleanField(default=True, help_text="Manual override to enable/disable voting")
    send_receipts = models.BooleanField(default=True, help_text="Send digital receipts after voting")
    accreditation_type = models.CharField(max_length=10, choices=ACCREDITATION_CHOICES, default='OTP')
    is_cleared = models.BooleanField(default=False, help_text="Superadmin clearance to go live")
    last_token_send_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Audit Integrity
    result_hash = models.CharField(max_length=64, null=True, blank=True, help_text="SHA-256 hash of the deterministic result ledger")
    is_sealed = models.BooleanField(default=False, help_text="True if results are final and immutable")

    def save(self, *args, **kwargs):
        if not self.short_id:
            import string, random
            while True:
                new_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                if not Election.objects.filter(short_id=new_id).exists():
                    self.short_id = new_id
                    break
        
        # Auto-clear contestant elections for immediate activation
        if self.election_type == 'CONTESTANT':
            self.is_cleared = True
            
        super().save(*args, **kwargs)

    def compute_result_hash(self):
        """Generates a deterministic SHA-256 hash of the election results."""
        import hashlib
        import json
        from .models import Vote
        
        # Serialize votes deterministically: [position_id, candidate_id] sorted
        votes = Vote.objects.filter(election=self).values('position_id', 'candidate_id').order_by('position_id', 'candidate_id')
        ledger_data = list(votes)
        ledger_str = json.dumps(ledger_data, sort_keys=True)
        
        return hashlib.sha256(ledger_str.encode('utf-8')).hexdigest()

    def seal_results(self):
        if self.status == 'CLOSED' and not self.is_sealed:
            self.result_hash = self.compute_result_hash()
            self.is_sealed = True
            self.save()

    def is_voting_allowed(self):
        now = timezone.now()
        if self.status != 'ACTIVE':
            return False, "Election is not active."
        if not self.is_voting_enabled:
            return False, "Voting is manually disabled by the organizer."
        if now < self.start_time:
            return False, "Voting has not started yet."
        if now > self.end_time:
            return False, "Voting has ended."
        return True, "Voting allowed."

    def __str__(self):
        return f"{self.title} ({self.institution.name})"

class Position(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.title} - {self.election.title}"

class Candidate(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    full_name = models.CharField(max_length=255)
    aka = models.CharField(max_length=100, blank=True, null=True, help_text="Popular Name")
    faculty = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)
    twitter = models.CharField(max_length=100, blank=True, null=True)
    tiktok = models.CharField(max_length=100, blank=True, null=True)
    instagram = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.full_name} ({self.position.title})"

class Voter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voter_profiles')
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='voters')
    matric_number = models.CharField(max_length=50)
    faculty = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    is_accredited = models.BooleanField(default=False)
    is_token_verified = models.BooleanField(default=False)
    has_voted = models.BooleanField(default=False)

    class Meta:
        unique_together = [('election', 'matric_number'), ('user', 'election')]
        indexes = [
            models.Index(fields=['user', 'election'], name='voter_user_election_idx'),
            models.Index(fields=['election', 'has_voted'], name='voter_election_voted_idx'),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.matric_number}"

class AllowedEmail(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    email = models.EmailField()
    
    class Meta:
        unique_together = ('election', 'email')

class ElectionToken(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='tokens')
    allowed_email = models.OneToOneField(AllowedEmail, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    resend_count = models.PositiveIntegerField(default=0)
    last_resend_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Token for {self.allowed_email.email} ({self.election.title})"

class Vote(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Contestant specific
    quantity = models.PositiveIntegerField(default=1)
    voter_name = models.CharField(max_length=255, null=True, blank=True)
    voter_email = models.EmailField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    paystack_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    signature = models.TextField(help_text="HMAC-SHA256 signature of the vote data", null=True, blank=True)
    verification_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    class Meta:
        permissions = [
            ("cannot_change_vote", "Can view but not change votes"),
        ]
        indexes = [
            models.Index(fields=['election', 'candidate'], name='vote_election_candidate_idx'),
            models.Index(fields=['election', 'position'], name='vote_election_position_idx'),
        ]

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.TextField(null=True, blank=True)
    extra_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action}"

class SystemConfig(models.Model):
    enable_otp_emails = models.BooleanField(default=True, help_text="Global switch for OTP verification emails")
    enable_receipt_emails = models.BooleanField(default=True, help_text="Global switch for voting receipt emails")
    
    # Contestant Charge Config
    # Example: [{"min": 200, "max": 1000, "percent": 0.10}]
    contest_charge_config = models.JSONField(default=list, help_text="Dynamic surcharge ranges for contestant votes")
    
    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configuration"

    def __str__(self):
        return "Global System Configuration"

    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(id=1)
        if not config.contest_charge_config:
            config.contest_charge_config = [
                {"min": 1, "max": 1000, "percent": 0.10},
                {"min": 1001, "max": 5000, "percent": 0.08},
                {"min": 5001, "max": None, "percent": 0.05}
            ]
            config.save()
        return config

class PlanPricing(models.Model):
    PLAN_CHOICES = (
        ('FREE', 'Free'),
        ('BASIC', 'Basic'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
    )
    plan_name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    price_per_email = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_emails = models.IntegerField(default=50, help_text="0 = unlimited")

    class Meta:
        verbose_name = "Plan Pricing"
        verbose_name_plural = "Plan Pricing"

    def __str__(self):
        return f"{self.get_plan_name_display()} - ₦{self.price_per_email}/email (max: {self.max_emails or 'Unlimited'})"

    @classmethod
    def initialize_defaults(cls):
        defaults = [
            {'plan_name': 'FREE', 'price_per_email': 0, 'max_emails': 50},
            {'plan_name': 'BASIC', 'price_per_email': 50, 'max_emails': 1000},
            {'plan_name': 'STANDARD', 'price_per_email': 40, 'max_emails': 5000},
            {'plan_name': 'PREMIUM', 'price_per_email': 35, 'max_emails': 0},
        ]
        for d in defaults:
            cls.objects.get_or_create(plan_name=d['plan_name'], defaults=d)

    @classmethod
    def get_all_plans(cls):
        cls.initialize_defaults()
        return cls.objects.all().order_by('price_per_email')

class ElectionPayment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='payments')
    plan = models.CharField(max_length=20, choices=Election.PLAN_CHOICES)
    email_count = models.IntegerField(default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paystack_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    paystack_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for {self.election.title} - {self.plan} - ₦{self.amount}"

class SentimentSurvey(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='surveys')
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, f"{i} Stars") for i in range(1, 6)])
    feedback = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('election', 'voter')

    def __str__(self):
        return f"Survey for {self.election.title} by {self.voter.username}"


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet: {self.user.email} - ₦{self.balance}"


class Withdrawal(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Withdrawal ₦{self.amount} - {self.wallet.user.email} ({self.status})"
