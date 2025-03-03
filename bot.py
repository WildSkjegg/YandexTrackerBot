import os
from typing import List, Tuple

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Конфигурация через Pydantic
class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = Field(..., alias="TELEGRAM_TOKEN")
    CHAT_ID: str = "-1002481390495"  # Основной чат
    MONITOR_CHATS: str = "-1002224942388,-1002481390495"  # Чаты для мониторинга
    DATABASE_PASSWORD: str = ""
    API_KEY: str = ""
    
    @property
    def target_chats(self):
        return self.MONITOR_CHATS.split(",")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Инициализация конфига
config = Settings()

# Настройка бота и диспетчера
bot = Bot(
    token=config.TELEGRAM_TOKEN,
    parse_mode=ParseMode.HTML,
    disable_web_page_preview=True
)
dp = Dispatcher(storage=MemoryStorage())

# Список команд для меню
COMMANDS: List[Tuple[str, str]] = [
    ("start", "Начать работу с ботом"),
    ("help", "Показать меню команд"),
    ("me", "Информация о пользователе"),
    ("task", "Все мои задачи"),
    ("crittask", "Критические задачи"),
    ("releasetask", "Релизные задачи")
]

# Обновим генерацию клавиатуры с проверкой прав
def get_main_keyboard(user_username: str) -> types.ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for cmd, _ in COMMANDS:
        # Показываем критические задачи только для QA
        if cmd == "crittask" and not user_username.startswith("@qa_"):
            continue
        builder.add(types.KeyboardButton(text=f"/{cmd}"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = f"@{message.from_user.username}" if message.from_user.username else ""
    await message.answer(
        'Привет! Я бот для работы с задачами. Вот доступные команды:',
        reply_markup=get_main_keyboard(username)
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = "<b>Доступные команды:</b>\n\n" + "\n".join(
        f"/{cmd} - {desc}" for cmd, desc in COMMANDS
    )
    await message.answer(help_text)

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

# Обновим структуру задач
tasks_data = {
    "#Крит_Блокер": [
        {
            "text": "Срочный баг в API",
            "link": "https://t.me/c/123456/789",
            "qa": "@ivan_qa"
        },
        {
            "text": "Проблема с авторизацией",
            "link": "https://t.me/c/123456/790",
            "qa": "@alex_qa"
        }
    ]
}

async def get_critical_tasks(user_username: str) -> List[dict]:
    """Возвращает задачи с проверкой QA"""
    return [
        task for task in tasks_data.get("#Крит_Блокер", [])
        if task["qa"].lower() == user_username.lower()
    ]

async def get_tasks_by_tag(tag: str) -> List[str]:
    """Временная заглушка для демонстрации"""
    return [
        "Тестовая задача 1",
        "Тестовая задача 2"
    ]

async def fetch_critical_tasks() -> List[dict]:
    """Собирает критические задачи из указанных чатов"""
    tasks = []
    for chat_id in config.target_chats:
        try:
            chat = await bot.get_chat(chat_id)
            if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                print(f"Чат {chat_id} не является группой/супергруппой")
                continue
                
            async for msg in bot.get_chat_history(
                chat_id=int(chat_id),
                limit=200
            ):
                if msg.text and any(tag in msg.text for tag in ["#Крит_Блокер", "#КритБлокер"]):
                    tasks.append({
                        "text": msg.text,
                        "link": f"https://t.me/c/{str(chat_id).replace('-100', '')}/{msg.message_id}",
                        "date": msg.date.strftime("%d.%m.%Y %H:%M")
                    })
                    
        except TelegramBadRequest as e:
            print(f"Ошибка доступа: {str(e)}")
        except Exception as e:
            print(f"Ошибка: {str(e)}")
    
    return sorted(tasks, key=lambda x: x['date'], reverse=True)[:10]

@dp.message(Command("crittask"))
async def cmd_critical_tasks(message: types.Message):
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        tasks = await fetch_critical_tasks()
        
        if not tasks:
            await message.answer("✅ Активных критических задач не найдено!")
            return

        builder = InlineKeyboardBuilder()
        response = ["🚨 <b>Критические задачи:</b>\n"]
        for idx, task in enumerate(tasks, 1):
            task_text = task['text'].replace('#Крит_Блокер', '🔥').replace('#КритБлокер', '🔥')
            response.append(
                f"{idx}. <b>Задача {idx}</b>\n"
                f"📅 {task['date']}\n"
                f"📝 {task_text[:150]}..."
            )
            builder.button(text=f"Задача {idx}", url=task['link'])

        builder.adjust(2)
        await message.answer(
            "\n".join(response),
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при получении задач!")

@dp.message(Command("task"))
async def cmd_all_tasks(message: types.Message):
    tasks = await get_tasks_by_tag("#ВсеЗадачи")
    response = "📋 Все ваши задачи:\n" + "\n".join(f"• {task}" for task in tasks)
    await message.answer(response)

@dp.message(Command("releasetask"))
async def cmd_release_tasks(message: types.Message):
    release_tags = ["#Релиз", "#Приемка", "#Быстрый_Тест"]
    tasks = []
    for tag in release_tags:
        tasks.extend(await get_tasks_by_tag(tag))
    
    if not tasks:
        await message.answer("📦 Нет активных релизных задач")
        return

    response = "🚀 Релизные задачи:\n" + "\n".join(
        f"✅ {task}" for task in tasks
    )
    await message.answer(response)

# Обработка ошибок
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    print(f"Ошибка: {exception}")
    return True

# Запуск бота
async def main():
    await bot.set_my_commands([types.BotCommand(command=cmd, description=desc) for cmd, desc in COMMANDS])
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 