from asgiref.sync import sync_to_async
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from .models import TelegramUser, SubscriptionChannel

MEMBER_STATUSES = {"member","administrator","creator"}

@sync_to_async
def get_or_create_tg_user(*, tg_id:int, username:str|None=None,
                          first_name:str|None=None, last_name:str|None=None,
                          language_code:str|None=None, is_premium:bool=False) -> TelegramUser:
    user, created = TelegramUser.objects.get_or_create(
        tg_id=tg_id,
        defaults=dict(
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_premium=bool(is_premium),
        ),
    )
    changed = False
    for field, value in dict(
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        is_premium=bool(is_premium),
    ).items():
        if value is not None and getattr(user, field) != value:
            setattr(user, field, value)
            changed = True
    if changed:
        user.save()
    return user


@sync_to_async
def get_required_channels():
    return list(SubscriptionChannel.objects.filter(is_active=True, is_required=True).order_by("sort_order", "title"))

async def check_user_subscriptions(bot: Bot, tg_user_id: int) -> tuple[bool, list[SubscriptionChannel]]:
    """
    Возвращает (подписан_на_все, список_на_которые_НЕ_подписан).
    """
    not_joined: list[SubscriptionChannel] = []
    for ch in await get_required_channels():
        try:
            member = await bot.get_chat_member(chat_id=ch.chat_id, user_id=tg_user_id)
            status = getattr(member, "status", None)
            if status not in MEMBER_STATUSES:
                not_joined.append(ch)
        except TelegramBadRequest:
            # бот не админ/нет доступа/канал приватный без инвайта и т.п.
            not_joined.append(ch)
    return (len(not_joined) == 0, not_joined)