from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Tuple, Optional

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.apps import apps

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN

CACHE_TTL = getattr(settings, "SUBSCRIPTION_CACHE_TTL", 300)
CACHE_PREFIX = "subs_check:v1"


@dataclass
class ChannelInfo:
    title: str
    chat_id: Optional[int] = None
    invite_link: Optional[str] = None  # @name без @ тоже допустим
    is_required: bool = True

def _normalize_username(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.strip()
    if not u:
        return None
    return u if u.startswith("@") else f"@{u}"

async def _check_one(bot: Bot, user_id: int, ch: ChannelInfo) -> Tuple[bool, Optional[str]]:
    """
    Возвращает (joined?, error_text_if_any).
    Любая ошибка проверки трактуется как not joined (если канал обязательный).
    """
    # Определяем идентификатор чата: chat_id или username
    chat_ref = ch.chat_id if ch.chat_id else ch.invite_link
    if not chat_ref:
        # если канал криво заполнен — считаем, что ОК для необязательного и не ОК для обязательного
        return (not ch.is_required, "channel ref is empty")

    try:
        member = await bot.get_chat_member(chat_id=chat_ref, user_id=user_id)
        status = getattr(member, "status", None)
        joined = status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
            # иногда Telegram возвращает RESTRICTED, но фактически пользователь член канала
            ChatMemberStatus.RESTRICTED,
        )
        return (joined or (not ch.is_required), None)
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        # Бот не состоит/нет прав/канал приватный/не найден — считаем НЕ подписан, если канал обязателен
        return ((not ch.is_required), str(e))
    except Exception as e:
        return ((not ch.is_required), f"unexpected: {e!r}")

async def _check_async(user_id: int):
    """
    Асинхронная проверка подписки с ORM через sync_to_async.
    """
    TelegramAdmin = apps.get_model("users", "SubscriptionChannel")

    # ORM-запрос через sync_to_async
    qs = await sync_to_async(list)(
        TelegramAdmin.objects.filter(is_active=True).order_by("sort_order", "id")
    )

    channels = [
        ChannelInfo(
            title=c.title,
            chat_id=c.chat_id if c.chat_id else None,
            invite_link=c.invite_link,
            is_required=c.is_required,
        )
        for c in qs
    ]

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    not_joined: List[dict] = []
    try:
        for ch in channels:
            ok_one, _err = await _check_one(bot, user_id, ch)
            if not ok_one and ch.is_required:
                not_joined.append({
                    "title": ch.title,
                    "chat_id": ch.chat_id,
                    "invite_link": ch.invite_link,
                })
        ok_all = len(not_joined) == 0
        return ok_all, not_joined
    finally:
        await bot.session.close()

def check_user_subscriptions_sync(
    user_id: int,
    *,
    use_cache: bool = True,
    force_refresh: bool = False
) -> Tuple[bool, List[dict]]:
    """
    Синхронная обёртка с кэшем.
    Кладём в кэш ПОЛНЫЙ результат (ok, not_joined), а не только bool.

    use_cache=False — отключить кэш (например, для теста).
    force_refresh=True — сбросить и пересчитать.
    """
    cache_key = f"{CACHE_PREFIX}:{user_id}"

    if use_cache and not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached  # (ok, not_joined)

    # обычный sync контекст
    res = asyncio.run(_check_async(user_id))

    if use_cache:
        cache.set(cache_key, res, CACHE_TTL)

    return res