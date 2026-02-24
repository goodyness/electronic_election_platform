from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailBackend(ModelBackend):
    """
    Custom authentication backend to allow login via email or username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            # This handles cases where 'username' might be passed as another keyword arg
            username = kwargs.get(UserModel.USERNAME_FIELD) or kwargs.get('email')
            
        try:
            # Try to find user by email
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            try:
                # Try to find user by username
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
