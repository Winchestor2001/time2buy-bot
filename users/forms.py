import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
from django import forms
from django.conf import settings

from bot.config import BOT_TOKEN
from users.models import TelegramAdmin, SubscriptionChannel

BUTTONS_HELP = (
    "Инлайн-кнопки в формате: каждая кнопка с новой строки, «Текст | URL». Пример:\n"
    "Каталог | https://example.com\n"
    "Написать | https://t.me/username"
)

class BroadcastForm(forms.Form):
    MEDIA_CHOICES = [
        ("text", "Только текст"),
        ("photo", "Фото"),
        ("video", "Видео"),
        ("animation", "GIF/Анимация"),
    ]

    media_type = forms.ChoiceField(label="Тип сообщения", choices=MEDIA_CHOICES, initial="text",
                                   widget=forms.Select(attrs={"class": "w-full"}))
    text = forms.CharField(label="Текст", required=False,
                           widget=forms.Textarea(attrs={"rows": 6, "class": "w-full"}))
    file = forms.FileField(label="Медиа-файл", required=False,
                           help_text="Фото/видео/гиф в зависимости от типа",
                           widget=forms.ClearableFileInput(attrs={"class": "w-full"}))
    buttons = forms.CharField(
        label="Кнопки", required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "w-full"}),
        help_text=BUTTONS_HELP,
    )

    def clean(self):
        cleaned = super().clean()
        mtype = cleaned.get("media_type")
        text = cleaned.get("text")
        file = cleaned.get("file")
        if mtype == "text" and not text:
            self.add_error("text", "Нужен текст для текстового сообщения.")
        if mtype != "text" and not file:
            self.add_error("file", "Для этого типа нужен загруженный файл.")
        return cleaned


class TelegramAdminForm(forms.ModelForm):
    class Meta:
        model = TelegramAdmin
        fields = ("username", "telegram_id", "is_active")

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get("username") or "").strip().lstrip("@")
        telegram_id = cleaned.get("telegram_id")

        # Нечего резолвить
        if telegram_id or not username:
            return cleaned

        token = BOT_TOKEN
        if not token:
            raise forms.ValidationError("BOT_TOKEN не задан в настройках проекта.")

        async def _resolve():
            bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                # get_chat принимает @username
                chat = await bot.get_chat(f"@{username}")
                return chat.id
            finally:
                await bot.session.close()

        # Запускаем асинхронный вызов безопасно из формы
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        try:
            if loop and loop.is_running():
                # редко для админки, но на всякий случай
                resolved_id = loop.run_until_complete(_resolve())  # type: ignore[attr-defined]
            else:
                resolved_id = asyncio.run(_resolve())
        except TelegramRetryAfter as e:
            raise forms.ValidationError(f"Telegram ограничил запрос. Повторите позже: retry_after={getattr(e, 'retry_after', 3)}с")
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            raise forms.ValidationError(f"Не удалось получить ID по username @{username}: {e}")
        except Exception as e:  # noqa: BLE001
            raise forms.ValidationError(f"Ошибка при определении telegram_id: {e}")

        cleaned["telegram_id"] = resolved_id
        cleaned["username"] = username
        return cleaned


class ChannelBroadcastForm(forms.Form):
    MEDIA_CHOICES = [
        ("text", "Только текст"),
        ("photo", "Фото"),
        ("video", "Видео"),
        ("animation", "GIF/Анимация"),
    ]

    media_type = forms.ChoiceField(label="Тип сообщения", choices=MEDIA_CHOICES, initial="text")
    text = forms.CharField(label="Текст", required=False, widget=forms.Textarea(attrs={"rows": 5}))
    file = forms.FileField(label="Медиа-файл", required=False, help_text="Фото/видео/гиф в зависимости от типа")
    buttons = forms.CharField(label="Кнопки", required=False, widget=forms.Textarea(attrs={"rows": 3}), help_text=BUTTONS_HELP)

    # ВЫБОР КАНАЛОВ
    channels = forms.ModelMultipleChoiceField(
        label="Каналы/группы для публикации",
        queryset=SubscriptionChannel.objects.none(),   # зададим в __init__
        required=False,
        help_text="Если ничего не выбрать — отправим во все активные каналы.",
        widget=forms.SelectMultiple(attrs={"size": 10}),
    )

    def __init__(self, *args, **kwargs):
        # Можно ограничить только активными
        qs = kwargs.pop("channels_qs", None)
        super().__init__(*args, **kwargs)
        self.fields["channels"].queryset = qs if qs is not None else SubscriptionChannel.objects.filter(is_active=True).order_by("sort_order", "title")

    def clean(self):
        cleaned = super().clean()
        mtype = cleaned.get("media_type")
        text = cleaned.get("text")
        file = cleaned.get("file")
        if mtype == "text" and not text:
            self.add_error("text", "Нужен текст для текстового сообщения.")
        if mtype != "text" and not file:
            self.add_error("file", "Для этого типа нужен загруженный файл.")
        return cleaned