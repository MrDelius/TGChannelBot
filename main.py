import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import TOKEN, LOG_LEVEL
from handlers import common, content, templates

async def setup_bot_commands(bot: Bot):
    """Создание меню команд (синяя кнопка '/' в Telegram)"""
    commands = [
        BotCommand(command="start", description="Запустить бота / Главное меню"),
        BotCommand(command="info", description="Инструкция по использованию"),
    ]
    await bot.set_my_commands(commands)

async def main():
    # 1. Настройка логирования
    # Берем уровень из config.py (по умолчанию INFO)
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    # 2. Инициализация бота
    # Используем DefaultBotProperties, чтобы все сообщения бота
    # по умолчанию поддерживали HTML-разметку
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # 3. Инициализация диспетчера
    dp = Dispatcher()

    # Установка меню команд в интерфейсе
    await setup_bot_commands(bot)

    # 4. Подключение роутеров
    # Важно: common подключаем первым, чтобы команда /start имела приоритет
    dp.include_router(common.router)
    dp.include_router(content.router)
    dp.include_router(templates.router)

    # 5. Очистка очереди обновлений
    # Удаляет все сообщения, которые прислали боту, пока он был выключен,
    # чтобы он не начал отвечать на них "пачкой" при запуске.
    await bot.delete_webhook(drop_pending_updates=True)

    # 6. Запуск бесконечного цикла опроса (Polling)
    print("🚀 Бот успешно запущен и готов к работе...")
    try:
        await dp.start_polling(bot)
    finally:
        # Корректное закрытие сессии бота при выключении
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен!")