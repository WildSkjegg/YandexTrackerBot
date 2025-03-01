import os
import logging
from typing import List, Tuple

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from pydantic_settings import BaseSettings

# Конфигурация через Pydantic
class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    DATABASE_PASSWORD: str = ""
    API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Инициализация конфига
config = Settings()

# Настройка бота и диспетчера
bot = Bot(token=config.TELEGRAM_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Список команд для меню
COMMANDS: List[Tuple[str, str]] = [
    ("start", "Начать работу с ботом"),
    ("help", "Показать меню команд"),
    ("info", "Информация о боте"),
    ("me", "Информация о пользователе")
]

# Генератор клавиатуры
def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for cmd, _ in COMMANDS:
        builder.add(types.KeyboardButton(text=f"/{cmd}"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        'Привет! Я простой бот. Вот доступные команды:',
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = "<b>Доступные команды:</b>\n\n" + "\n".join(
        f"/{cmd} - {desc}" for cmd, desc in COMMANDS
    )
    await message.answer(help_text)

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    info_text = """
🚀 <b>Я бот для Yandex Tracker</b>
✅ Готов к работе в любое время!
"""
    await message.answer(info_text)

@dp.message(Command("me"))
async def cmd_me(message: types.Message):
    user = message.from_user
    user_info = (
        "<b>Информация о вас:</b>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.first_name}\n"
        f"👥 Фамилия: {user.last_name or 'не указана'}\n"
        f"📛 Username: @{user.username or 'не указан'}\n"
        f"🌐 Язык: {user.language_code or 'не указан'}"
    )
    await message.answer(user_info)

# Обработка ошибок
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    logger.error(f"Ошибка при обработке {update}: {exception}")
    return True

# Запуск бота
async def main():
    await bot.set_my_commands([types.BotCommand(command=cmd, description=desc) for cmd, desc in COMMANDS])
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 