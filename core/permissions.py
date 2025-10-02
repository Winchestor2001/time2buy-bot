from rest_framework.permissions import BasePermission
from rest_framework.exceptions import APIException
from rest_framework import status
from django.conf import settings

from users.subscriptions import check_user_subscriptions_sync

class SubscriptionRequired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "subscription_required"

    def __init__(self, channels):
        detail = {
            "detail": "subscription_required",
            "channels": [
                {"title": c.title, "link": c.link} for c in channels
            ],
        }
        super().__init__(detail=detail)


class IsSubscribed(BasePermission):
    """
    Глобальная проверка подписки.
    - Если вьюха поставит `skip_subscription = True` — проверка пропустится.
    - user_id берём из заголовка `X-Tg-User-Id` или query `user_id`.
    - Если нет user_id — пропускаем (не мешаем открытым эндпоинтам).
    """

    def has_permission(self, request, view):
        if getattr(view, "skip_subscription", False):
            return True

        if not getattr(settings, "SUBSCRIPTION_ENFORCED", True):
            return True

        user_id = request.headers.get("X-Tg-User-Id") or request.query_params.get("user_id")
        if not user_id:
            return True  # не знаем юзера — не блокируем

        try:
            uid = int(user_id)
        except Exception:
            return True

        ok, not_joined = check_user_subscriptions_sync(uid)
        if ok:
            return True
        raise SubscriptionRequired(channels=not_joined)