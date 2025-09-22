import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.core.management.base import BaseCommand
from bot.handlers import router

from bot.config import BOT_TOKEN

class Command(BaseCommand):
    help = "Run Telegram bot (aiogram 3) with polling"

    def handle(self, *args, **kwargs):
        asyncio.run(self.main())

    async def main(self):
        dp = Dispatcher()
        dp.include_router(router)
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.stdout.write(self.style.SUCCESS("Бот запущен. Нажмите Ctrl+C для остановки."))
        await dp.start_polling(bot)