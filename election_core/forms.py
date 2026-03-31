from django import forms
from django.contrib.auth import get_user_model
from .models import Institution, Voter, Candidate, Position, Election, AllowedEmail

User = get_user_model()

class OrganizerRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'contact', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class OTPVerificationForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput())
    otp_code = forms.CharField(max_length=6, min_length=6, label="Enter 6-digit OTP")

class VoterAccreditationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(is_active=True), 
        required=True, 
        empty_label="Select your Institution"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'institution']

    def __init__(self, *args, **kwargs):
        self.election = kwargs.pop('election', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        institution = cleaned_data.get("institution")
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        if self.election:
            # 1. Check if email is in allowed_email for this election
            is_allowed = AllowedEmail.objects.filter(election=self.election, email__iexact=email).exists()
            if not is_allowed:
                raise forms.ValidationError(f"The email {email} is not authorized for this election. Please contact the organizer.")

            # 2. Check if selected institution matches the election's institution
            if self.election.institution and institution != self.election.institution:
                raise forms.ValidationError(f"This election is restricted to students of {self.election.institution.name}. Please select the correct institution.")
            
        return cleaned_data
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if email:
            # Check if user exists
            if User.objects.filter(email=email).exists():
                # Existing user - passwords not required
                pass
            else:
                # New user - passwords required
                if not password or not confirm_password:
                    raise forms.ValidationError("Password is required for new registration.")
                if password != confirm_password:
                    raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return email

class VoterDetailsForm(forms.ModelForm):
    class Meta:
        model = Voter
        fields = ['matric_number', 'faculty', 'department']

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label="Enter your registered email")

class PasswordResetForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput())
    otp_code = forms.CharField(max_length=6, min_length=6, label="6-Digit OTP Code")
    new_password = forms.CharField(widget=forms.PasswordInput, label="New Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm New Password")

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ['name', 'is_active']

class ElectionForm(forms.ModelForm):
    institution = forms.ModelChoiceField(queryset=Institution.objects.filter(is_active=True), required=True)

    class Meta:
        model = Election
        fields = ['title', 'institution', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class ContestantElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'voting_fee', 'description', 'contest_image', 'start_time', 'end_time', 'custom_slug']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        help_texts = {
            'custom_slug': 'Unique URL for your contest, e.g. "most-handsome-2024"',
        }

    def clean_custom_slug(self):
        slug = self.cleaned_data.get('custom_slug')
        if slug:
            # Check for uniqueness, excluding current instance if editing
            if Election.objects.filter(custom_slug=slug).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("This custom link is already in use. Please choose another one.")
            
            # Simple alphanumeric/hyphen validation (SlugField handles most)
            import re
            if not re.match(r'^[a-z0-9-]+$', slug):
                raise forms.ValidationError("Custom link can only contain lowercase letters, numbers, and hyphens.")
        return slug

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'order']

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['full_name', 'aka', 'faculty', 'department', 'bio', 'photo', 'twitter', 'tiktok', 'instagram']

class ContestantForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['full_name', 'bio', 'photo', 'twitter', 'tiktok', 'instagram']

class AllowedEmailForm(forms.ModelForm):
    class Meta:
        model = AllowedEmail
        fields = ['email']

class BulkUploadForm(forms.Form):
    csv_file = forms.FileField(label="Select CSV File", help_text="Upload a CSV file containing email addresses in the first column.")
