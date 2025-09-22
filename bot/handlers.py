import os
from aiogram import Router, F
from aiogram.types import (
    Message,
    MenuButtonWebApp, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hlink

from bot.config import WEBAPP_URL
from users.services import get_or_create_tg_user, check_user_subscriptions

router = Router()



def build_subs_keyboard(channels) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        link = ch.public_link or "#"
        text = f"Подписаться: {ch.title}"
        rows.append([InlineKeyboardButton(text=text, url=link)])
    rows.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="subs:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    # 1) создать/обновить пользователя в БД
    await get_or_create_tg_user(
        tg_id=u.id,
        username=u.username,
        first_name=u.first_name,
        last_name=u.last_name,
        language_code=u.language_code,
        is_premium=getattr(u, "is_premium", False),
    )

    # 2) установить кнопку WebApp в меню
    await message.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🛍 Открыть магазин", web_app=WebAppInfo(url=WEBAPP_URL))
    )

    # 3) проверить подписки
    ok, not_joined = await check_user_subscriptions(message.bot, u.id)
    if not ok:
        text = (
            "Для продолжения подпишитесь на каналы ниже и нажмите "
            f"{hlink('«✅ Я подписался»', '#')} для проверки."
        )
        await message.answer(text, reply_markup=build_subs_keyboard(not_joined))
        return

    # 4) добро пожаловать
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}! 👋\n"
        "❓ Есть вопрос или предложение? Связаться с администрацией можно по соответствующей кнопке\n"
        "Проблемы с ботом? Пропишите /start для перезапуска или свяжитесь с администрацией",
    )


@router.callback_query(F.data == "subs:recheck")
async def subs_recheck(cq: CallbackQuery):
    ok, not_joined = await check_user_subscriptions(cq.bot, cq.from_user.id)
    if ok:
        await cq.message.edit_text("Спасибо! Подписка подтверждена. Откройте магазин через кнопку меню «🛍 Открыть магазин». ✅")
    else:
        await cq.answer("Ещё не все подписки оформлены", show_alert=True)
        await cq.message.edit_reply_markup(reply_markup=build_subs_keyboard(not_joined))