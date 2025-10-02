from django.urls import path

from users.views import SubscriptionCheckView

urlpatterns = [
    path("subscriptions/check/", SubscriptionCheckView.as_view()),
]