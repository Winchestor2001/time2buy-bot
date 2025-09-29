from django.contrib import admin, messages
from django.contrib.auth.models import Group, User
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from django.urls import path
from unfold.admin import ModelAdmin

from .broadcast import send_broadcast_sync
from .forms import BroadcastForm, TelegramAdminForm
from .models import TelegramUser, SubscriptionChannel, TelegramAdmin

# Спрятать системную модель групп
try:
    admin.site.unregister(User)
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(ModelAdmin):
    pass


@admin.register(TelegramUser)
class TelegramUserAdmin(ModelAdmin):
    change_list_template = "admin/users/telegramuser/change_list.html"
    list_display = ("id","tg_id","username","first_name","is_blocked","created_at")
    list_display_links = ("tg_id","username","first_name")
    search_fields = ("tg_id","username","first_name","last_name")
    list_filter = ("is_premium","is_blocked","language_code")
    readonly_fields = ("created_at","updated_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # полностью отключаем кнопку "Добавить"
        return False

    # --- кастомный URL для формы рассылки ---
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("broadcast/", self.admin_site.admin_view(self.broadcast_view), name="users_telegramuser_broadcast"),
        ]
        return custom + urls

    # добавим кнопку в верхние object-tools (Unfold подхватит)
    def changelist_view(self, request, extra_context=None):
        extra = extra_context or {}
        extra["object_tools"] = [{
            "label": "📣 Рассылка",
            "url": "broadcast/",
            "class": "btn btn-primary",
            "target": "_self",
            "permissions": ["change"],
        }]
        return super().changelist_view(request, extra_context=extra)

    # сама форма и обработчик
    def broadcast_view(self, request):
        form = BroadcastForm(request.POST or None, request.FILES or None)

        if request.method == "POST" and form.is_valid():
            media_type = form.cleaned_data["media_type"]
            text = form.cleaned_data.get("text")
            file = form.cleaned_data.get("file")
            buttons = form.cleaned_data.get("buttons")

            # рассылаем всем
            chat_ids = list(TelegramUser.objects.values_list("tg_id", flat=True))

            file_path = None
            if file:
                save_path = default_storage.save(f"broadcast/{file.name}", file)
                file_path = default_storage.path(save_path)

            send_broadcast_sync(
                media_type=media_type,
                text=text,
                file_path=file_path,
                buttons_raw=buttons,
                chat_ids=chat_ids,
            )
            messages.success(request, f"✅ Рассылка успешно отправлена ({len(chat_ids)} получателей).")
            return redirect("admin:users_telegramuser_changelist")

        context = self.admin_site.each_context(request)
        context.update({
            "title": "📣 Массовая рассылка",
            "opts": self.model._meta,
            "has_view_permission": True,
            "has_change_permission": True,
            "has_module_permission": True,
            "form": form,
        })
        return render(request, "admin/broadcast_form.html", context)


@admin.register(SubscriptionChannel)
class SubscriptionChannelAdmin(ModelAdmin):
    list_display = ("id","title","chat_id","username","is_group","is_required","is_active","sort_order")
    list_display_links = ("title","chat_id","username")
    list_editable = ("is_required","is_active","sort_order")
    search_fields = ("title","username","chat_id")
    list_filter = ("is_group","is_required","is_active")
    ordering = ("sort_order","title")


@admin.action(description="Определить telegram_id по username для выбранных")
def resolve_ids(modeladmin, request, queryset):
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from django.conf import settings
    import asyncio
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        messages.error(request, "BOT_TOKEN не задан в настройках.")
        return

    async def _job(objs):
        bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
        ok, fail = 0, 0
        try:
            for obj in objs:
                if obj.telegram_id or not obj.username:
                    continue
                try:
                    chat = await bot.get_chat(f"@{obj.username.lstrip('@')}")
                    obj.telegram_id = chat.id
                    obj.save(update_fields=["telegram_id"])
                    ok += 1
                except TelegramRetryAfter as e:
                    # подождём и повторим один раз
                    await asyncio.sleep(getattr(e, "retry_after", 3) or 3)
                    try:
                        chat = await bot.get_chat(f"@{obj.username.lstrip('@')}")
                        obj.telegram_id = chat.id
                        obj.save(update_fields=["telegram_id"])
                        ok += 1
                    except Exception:
                        fail += 1
                except (TelegramBadRequest, TelegramForbiddenError):
                    fail += 1
                except Exception:
                    fail += 1
        finally:
            await bot.session.close()
        return ok, fail

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        ok, fail = loop.run_until_complete(_job(list(queryset)))  # type: ignore[attr-defined]
    else:
        ok, fail = asyncio.run(_job(list(queryset)))

    messages.info(request, f"Готово: успешно={ok}, ошибок={fail}")

@admin.register(TelegramAdmin)
class TelegramAdminAdmin(ModelAdmin):
    form = TelegramAdminForm
    list_display = ("id", "username", "telegram_id", "is_active", "created_at")
    list_editable = ("is_active",)
    search_fields = ("username", "telegram_id")
    ordering = ("-id",)
    actions = [resolve_ids]