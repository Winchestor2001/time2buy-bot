# users/broadcast.py
from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from aiogram.client.default import DefaultBotProperties
from django.conf import settings

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

logger = logging.getLogger(__name__)


# =========================
# Вспомогательные сущности
# =========================

@dataclass
class BroadcastResult:
    total: int
    ok: int
    failed: int


def _resolve_bot_token(explicit: Optional[str] = None) -> str:
    """
    Возвращает токен бота с приоритетом:
      1) явный аргумент,
      2) settings.BOT_TOKEN,
      3) bot.config.BOT_TOKEN (если модуль существует),
      4) переменная окружения BOT_TOKEN.
    """
    if explicit:
        return explicit

    token = getattr(settings, "BOT_TOKEN", None)
    if token:
        return token

    # Пытаемся подтянуть из bot.config, если есть.
    try:
        from bot.config import BOT_TOKEN as CFG_TOKEN  # type: ignore
    except Exception:
        CFG_TOKEN = None

    token = CFG_TOKEN or os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN не найден. Укажите его в settings.BOT_TOKEN, "
            "или в bot.config.BOT_TOKEN, или в переменной окружения BOT_TOKEN."
        )
    return token


def _make_file(path: str | Path) -> FSInputFile:
    """Готовим файловый объект для aiogram v3 (локальный файл)."""
    p = Path(path)
    return FSInputFile(p.as_posix(), filename=p.name)


def _parse_buttons(raw: Optional[str]) -> list[list[InlineKeyboardButton]]:
    """
    Разбирает строки вида:
      Каталог | https://example.com
      Написать | https://t.me/username
    Каждая строка = отдельная кнопка (в один столбец).
    """
    if not raw:
        return []
    rows: list[list[InlineKeyboardButton]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            logger.warning("Некорректная кнопка: %r (ожидалось 'Текст | URL')", line)
            continue
        text, url = parts
        rows.append([InlineKeyboardButton(text=text, url=url)])
    return rows


def _build_markup(raw_buttons: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    rows = _parse_buttons(raw_buttons)
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# Непосредственная отправка
# =========================

async def _send_one(
    bot: Bot,
    chat_id: int,
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    markup: Optional[InlineKeyboardMarkup],
):
    """Отправляет одно сообщение выбранного типа."""
    if media_type == "text":
        return await bot.send_message(
            chat_id,
            text or "",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    if not file_path:
        # Если тип медиа, а файл не приложили — не падаем.
        return await bot.send_message(
            chat_id,
            text or "[Файл не приложен]",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    fs = _make_file(file_path)

    if media_type == "photo":
        return await bot.send_photo(chat_id, photo=fs, caption=text or "", reply_markup=markup)
    if media_type == "video":
        return await bot.send_video(chat_id, video=fs, caption=text or "", reply_markup=markup)
    if media_type == "animation":  # gif
        return await bot.send_animation(chat_id, animation=fs, caption=text or "", reply_markup=markup)

    # Fallback
    return await bot.send_message(chat_id, text or "", reply_markup=markup)


async def _worker(
    bot: Bot,
    chat_ids: Iterable[int],
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    markup: Optional[InlineKeyboardMarkup],
    result: BroadcastResult,
):
    """Линейная рассылка с уважением RetryAfter и обработкой блокировок."""
    for chat_id in chat_ids:
        try:
            await _send_one(bot, chat_id, media_type, text, file_path, markup)
            result.ok += 1
        except TelegramRetryAfter as e:
            sleep_for = int(getattr(e, "retry_after", 3)) or 3
            logger.warning("429 RetryAfter (sleep %ss) для chat_id=%s", sleep_for, chat_id)
            await asyncio.sleep(sleep_for)
            try:
                await _send_one(bot, chat_id, media_type, text, file_path, markup)
                result.ok += 1
            except Exception as e2:  # noqa: BLE001
                result.failed += 1
                logger.exception("Повтор не удался для %s: %s", chat_id, e2)
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            result.failed += 1
            logger.warning("Не удалось отправить %s (%s): %s", chat_id, type(e).__name__, e)
        except Exception as e:  # noqa: BLE001
            result.failed += 1
            logger.exception("Ошибка при отправке %s: %s", chat_id, e)


async def _send_broadcast_async(
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    buttons_raw: Optional[str],
    chat_ids: list[int],
    bot_token: Optional[str] = None,
) -> BroadcastResult:
    """
    Асинхронная рассылка.
    media_type: "text" | "photo" | "video" | "animation"
    """
    token = _resolve_bot_token(bot_token)
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    markup = _build_markup(buttons_raw)

    result = BroadcastResult(total=len(chat_ids), ok=0, failed=0)
    try:
        await _worker(bot, chat_ids, media_type, text, file_path, markup, result)
    finally:
        await bot.session.close()
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
                logger.info("Файл %s удалён после рассылки", file_path)
            except Exception as e:
                logger.warning("Не удалось удалить файл %s: %s", file_path, e)

    return result


# =========================
# Синхронная обёртка (для админки)
# =========================

def send_broadcast_sync(
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    buttons_raw: Optional[str],
    chat_ids: list[int],
    bot_token: Optional[str] = None,
) -> BroadcastResult:
    """
    Синхронная обёртка над рассылкой.
    Возврат: BroadcastResult(total, ok, failed).
    """
    logger.info(
        "Запуск рассылки: type=%s, file=%s, recipients=%d",
        media_type, file_path, len(chat_ids),
    )
    return asyncio.run(
        _send_broadcast_async(
            media_type=media_type,
            text=text,
            file_path=file_path,
            buttons_raw=buttons_raw,
            chat_ids=chat_ids,
            bot_token=bot_token,
        )
    )