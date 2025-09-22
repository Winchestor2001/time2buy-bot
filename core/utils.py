from django.conf import settings
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadData
from rest_framework.reverse import reverse_lazy


def get_reverse_link(app_name: str, model_name: str):
    return reverse_lazy(f"admin:{app_name}_{model_name}_changelist")


def generate_token():
    return URLSafeTimedSerializer(settings.SECRET_KEY)


def verify_token(token):
    serializer = generate_token()
    try:
        email = serializer.loads(token, salt="password-recovery", max_age=600)
        return email
    except SignatureExpired:
        raise ValueError("The link has expired.")
    except BadData:
        raise ValueError("Invalid link.")