from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse
from shop.analytics import get_kpis

@staff_member_required
def analytics_dashboard(request):
    ctx = admin.site.each_context(request)
    data = get_kpis()
    ctx.update({
        "title": "Аналитика",
        "data": data,
    })
    return render(request, "admin/analytics/dashboard.html", ctx)

# опционально: мягкий редирект с корня админки на дашборд
@staff_member_required
def admin_root_redirect(request):
    return redirect(reverse("admin-analytics"))