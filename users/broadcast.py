import os, asyncio
from typing import Iterable, List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from asgiref.sync import async_to_sync

from bot.config import BOT_TOKEN


def parse_buttons(raw: str) -> InlineKeyboardMarkup | None:
    if not raw:
        return None
    rows: List[List[InlineKeyboardButton]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            text, url = [p.strip() for p in line.split("|", 1)]
        else:
            text, url = line, line
        rows.append([InlineKeyboardButton(text=text, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

async def _send_async(media_type: str, text: str | None, file_path: str | None,
                      buttons_markup: InlineKeyboardMarkup | None,
                      chat_ids: Iterable[int]):
    bot = Bot(token=BOT_TOKEN)
    try:
        # Рассылаем с мягким rate-limit
        for uid in chat_ids:
            try:
                if media_type == "text":
                    await bot.send_message(uid, text or "", reply_markup=buttons_markup)
                elif media_type == "photo":
                    await bot.send_photo(uid, InputFile(file_path), caption=text or "", reply_markup=buttons_markup)
                elif media_type == "video":
                    await bot.send_video(uid, InputFile(file_path), caption=text or "", reply_markup=buttons_markup)
                elif media_type == "animation":
                    await bot.send_animation(uid, InputFile(file_path), caption=text or "", reply_markup=buttons_markup)
            except Exception:
                # не валим рассылку из-за ошибки одного пользователя
                pass
            await asyncio.sleep(0.05)  # ~20 msg/сек — безопаснее
    finally:
        await bot.session.close()

def send_broadcast_sync(*, media_type: str, text: str | None,
                        file_path: str | None, buttons_raw: str | None,
                        chat_ids: Iterable[int]):
    markup = parse_buttons(buttons_raw or "")
    async_to_sync(_send_async)(media_type, text, file_path, markup, chat_ids)