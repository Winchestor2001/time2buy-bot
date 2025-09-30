from datetime import timedelta
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from shop.models import Order, OrderItem, Product
from users.models import TelegramUser

def get_kpis():
    now = timezone.now()
    today_start = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)
    d14 = now - timedelta(days=14)

    # агрегаты по заказам
    qs_all = Order.objects.all()
    qs_today = Order.objects.filter(created_at__gte=today_start)
    qs_7 = Order.objects.filter(created_at__gte=d7)
    qs_30 = Order.objects.filter(created_at__gte=d30)

    total_orders = qs_all.count()
    revenue_total = qs_all.aggregate(s=Sum("total_amount"))["s"] or 0
    revenue_today = qs_today.aggregate(s=Sum("total_amount"))["s"] or 0
    revenue_7 = qs_7.aggregate(s=Sum("total_amount"))["s"] or 0
    revenue_30 = qs_30.aggregate(s=Sum("total_amount"))["s"] or 0

    aov = (revenue_total / total_orders) if total_orders else 0

    # статус-микс
    status_mix = list(
        qs_all.values("status").annotate(c=Count("id")).order_by("-c")
    )

    # продажи по дням за 14 дней (для графика)
    sales_by_day = (
        Order.objects.filter(created_at__date__gte=d14.date())
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(amount=Sum("total_amount"))
        .order_by("day")
    )
    chart_labels = [r["day"].strftime("%d.%m") for r in sales_by_day]
    chart_values = [float(r["amount"] or 0) for r in sales_by_day]

    # топ-продукты
    top_products = list(
        OrderItem.objects
        .values("product_id", "product__name")
        .annotate(qty=Sum("quantity"), sales=Sum(F("quantity") * F("price")))
        .order_by("-qty")[:10]
    )

    # топ-категории
    top_categories = list(
        OrderItem.objects
        .values("product__category_id", "product__category__name")
        .annotate(qty=Sum("quantity"), sales=Sum(F("quantity") * F("price")))
        .order_by("-qty")[:10]
    )

    # пользователи
    new_users_7 = TelegramUser.objects.filter(created_at__gte=d7).count()
    new_users_30 = TelegramUser.objects.filter(created_at__gte=d30).count()
    users_total = TelegramUser.objects.count()

    return {
        "kpi": {
            "revenue_total": revenue_total,
            "revenue_today": revenue_today,
            "revenue_7": revenue_7,
            "revenue_30": revenue_30,
            "total_orders": total_orders,
            "aov": aov,
            "users_total": users_total,
            "new_users_7": new_users_7,
            "new_users_30": new_users_30,
        },
        "status_mix": status_mix,
        "chart": {"labels": chart_labels, "values": chart_values},
        "top_products": top_products,
        "top_categories": top_categories,
    }