from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from bot.config import BOT_TOKEN

logger = logging.getLogger(__name__)


@dataclass
class BroadcastResult:
    total: int
    ok: int
    failed: int


def _make_file(path: str | Path) -> FSInputFile:
    p = Path(path)
    return FSInputFile(p.as_posix(), filename=p.name)


def _parse_buttons(raw: Optional[str]) -> list[list[InlineKeyboardButton]]:
    if not raw:
        return []
    rows: list[list[InlineKeyboardButton]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if len(parts) != 2:
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


async def _send_one(
    bot: Bot,
    chat_id: int,
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    markup: Optional[InlineKeyboardMarkup],
):
    if media_type == "text":
        return await bot.send_message(chat_id, text or "", reply_markup=markup, disable_web_page_preview=True)

    if not file_path:
        return await bot.send_message(chat_id, text or "[Файл не приложен]", reply_markup=markup, disable_web_page_preview=True)

    fs = _make_file(file_path)

    if media_type == "photo":
        return await bot.send_photo(chat_id, photo=fs, caption=text or "", reply_markup=markup)
    if media_type == "video":
        return await bot.send_video(chat_id, video=fs, caption=text or "", reply_markup=markup)
    if media_type == "animation":
        return await bot.send_animation(chat_id, animation=fs, caption=text or "", reply_markup=markup)

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
    for chat_id in chat_ids:
        try:
            await _send_one(bot, chat_id, media_type, text, file_path, markup)
            result.ok += 1
        except TelegramRetryAfter as e:
            sleep_for = int(getattr(e, "retry_after", 3)) or 3
            await asyncio.sleep(sleep_for)
            try:
                await _send_one(bot, chat_id, media_type, text, file_path, markup)
                result.ok += 1
            except Exception:
                result.failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            result.failed += 1
        except Exception:
            result.failed += 1


async def _send_channel_broadcast_async(
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    buttons_raw: Optional[str],
    chat_ids: list[int],
) -> BroadcastResult:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не настроен")

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    markup = _build_markup(buttons_raw)

    result = BroadcastResult(total=len(chat_ids), ok=0, failed=0)
    try:
        await _worker(bot, chat_ids, media_type, text, file_path, markup, result)
    finally:
        await bot.session.close()

    return result


def send_channel_broadcast_sync(
    media_type: str,
    text: Optional[str],
    file_path: Optional[str],
    buttons_raw: Optional[str],
    chat_ids: list[int],
) -> BroadcastResult:
    logger.info("Рассылка в каналы: type=%s, file=%s, recipients=%d", media_type, file_path, len(chat_ids))
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # В админке обычно нет активного цикла, но на всякий случай:
        return loop.run_until_complete(  # type: ignore[attr-defined]
            _send_channel_broadcast_async(media_type, text, file_path, buttons_raw, chat_ids)
        )

    return asyncio.run(
        _send_channel_broadcast_async(media_type, text, file_path, buttons_raw, chat_ids)
    )