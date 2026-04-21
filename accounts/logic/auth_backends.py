from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using either 
    their email address or their username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        # If username is None, check kwargs (sometimes passed this way)
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        try:
            # Check for a user with the provided identifier in either username or email fields
            user = UserModel.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).distinct()
        except UserModel.DoesNotExist:
            return None

        if user.exists():
            user_obj = user.first()
            if user_obj.check_password(password) and self.user_can_authenticate(user_obj):
                return user_obj
        
        return None
