import asyncio
from typing import List, Iterable

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from django.conf import settings
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadData
from rest_framework.reverse import reverse_lazy
from django.apps import apps

from bot.config import BOT_TOKEN


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


def _get_admin_chat_ids() -> List[int]:
    """СИНХРОННО: достаём список chat_id админов из БД (ORM трогаем только тут)."""
    TelegramAdmin = apps.get_model("users", "TelegramAdmin")
    return list(
        TelegramAdmin.objects
        .filter(is_active=True, telegram_id__isnull=False)
        .values_list("telegram_id", flat=True)
    )


async def _notify_admins_async(text: str, chat_ids: Iterable[int]):
    if not BOT_TOKEN:
        return
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        for chat_id in chat_ids:
            if not chat_id:
                continue
            try:
                await bot.send_message(chat_id, text, disable_web_page_preview=True)
            except TelegramRetryAfter as e:
                # подождём и попробуем ещё раз
                await asyncio.sleep(getattr(e, "retry_after", 3) or 3)
                try:
                    await bot.send_message(chat_id, text, disable_web_page_preview=True)
                except Exception:
                    pass
            except (TelegramForbiddenError, TelegramBadRequest):
                # заблокировал/некорректный чат — пропускаем
                pass
            except Exception:
                pass
    finally:
        await bot.session.close()

def notify_admins(text: str) -> None:
    """
    Безопасная обёртка:
    1) синхронно берём chat_ids из БД;
    2) асинхронно шлём сообщения (через существующий loop или создаём новый).
    """
    chat_ids = _get_admin_chat_ids()  # <-- ORM тут, в sync-коде

    if not chat_ids:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # если уже находимся в async-контексте — просто запускаем таск
        asyncio.create_task(_notify_admins_async(text, chat_ids))
    else:
        # обычный sync-контекст (DRF view) — создаём новый loop
        asyncio.run(_notify_admins_async(text, chat_ids))