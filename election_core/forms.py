from django import forms
from django.contrib.auth import get_user_model
from .models import Institution, Voter, Candidate, Position, Election, AllowedEmail

User = get_user_model()

class OrganizerRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    institution = forms.ModelChoiceField(queryset=Institution.objects.filter(is_active=True))

    class Meta:
        model = User
        fields = ['email', 'contact']

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
    institution = forms.ModelChoiceField(queryset=Institution.objects.filter(is_active=True))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
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
    class Meta:
        model = Election
        fields = ['title', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'order']

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['full_name', 'aka', 'faculty', 'department', 'bio', 'photo']

class AllowedEmailForm(forms.ModelForm):
    class Meta:
        model = AllowedEmail
        fields = ['email']

class BulkUploadForm(forms.Form):
    csv_file = forms.FileField(label="Select CSV File", help_text="Upload a CSV file containing email addresses in the first column.")
