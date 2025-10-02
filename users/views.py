from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.subscriptions import check_user_subscriptions_sync


class SubscriptionCheckView(APIView):
    """
    GET /api/subscriptions/check/?user_id=123
    """
    permission_classes = [permissions.AllowAny]
    skip_subscription = True  # <- пропускаем глобальную проверку

    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            uid = int(user_id)
        except Exception:
            return Response({"detail": "user_id must be int"}, status=status.HTTP_400_BAD_REQUEST)
        ok, not_joined = check_user_subscriptions_sync(uid)
        return Response({
            "ok": ok,
            "not_joined": [{"title": c['title'], "link": c['invite_link']} for c in not_joined]
        })
