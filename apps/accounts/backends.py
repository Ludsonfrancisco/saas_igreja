from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Autentica por email (case-insensitive).

    Django passa o valor de USERNAME_FIELD como `username`; aceitamos tanto
    `email` quanto `username` como o endereco de email (P-ARQ-03 / SEC-02).
    """

    def authenticate(self, request, username=None, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        email = email or username
        if email is None or password is None:
            return None
        try:
            user = UserModel._default_manager.get(email__iexact=email)
        except UserModel.DoesNotExist:
            # Roda o hasher mesmo sem usuario para mitigar timing attacks.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
