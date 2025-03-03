import os
import logging
from typing import List, Tuple
import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Конфигурация через Pydantic
class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = Field(..., alias="TELEGRAM_TOKEN")
    CHAT_ID: str = "-1002481390495"  # Основной чат
    MONITOR_CHATS: str = "-1002224942388,-1002481390495"  # Чаты для мониторинга
    # Параметры для будущего расширения (например, база данных)
    DATABASE_PASSWORD: str = ""
    API_KEY: str = ""

    @property
    def target_chats(self) -> List[str]:
        return [chat.strip() for chat in self.MONITOR_CHATS.split(",") if chat.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Инициализация конфига, бота и диспетчера
try:
    config = Settings()
except Exception as e:
    logger.critical(f"Ошибка загрузки настроек: {e}")
    raise

bot = Bot(
    token=config.TELEGRAM_TOKEN,
    parse_mode=ParseMode.HTML,
    disable_web_page_preview=True
)
dp = Dispatcher(storage=MemoryStorage())


# Обновление списка команд для расширенного функционала
COMMANDS: List[Tuple[str, str]] = [
    ("start", "Начать работу с ботом"),
    ("help", "Показать меню команд"),
    ("me", "Информация о пользователе"),
    ("task", "Список всех ваших задач"),
    ("crittask", "Критические задачи"),
    ("bloker", "Блокирующие задачи"),
    ("releasetask", "Задачи для релиза"),
    ("admin", "Панель администратора"),
    ("reminder", "Установить напоминание"),
    ("stats", "Аналитика задач"),
    ("external", "Интеграция с внешними сервисами"),
    ("settings", "Настройки пользователя")
]


# Функция генерации основной клавиатуры
def get_main_keyboard(user_username: str) -> types.ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for cmd, _ in COMMANDS:
        builder.add(types.KeyboardButton(text=f"/{cmd}"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = f"@{message.from_user.username}" if message.from_user.username else ""
    text = 'Привет! Я бот для управления задачами. Вот доступные команды:'
    await message.answer(text, reply_markup=get_main_keyboard(username))


# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = "<b>Доступные команды:</b>\n\n" + "\n".join(
        f"/{cmd} - {desc}" for cmd, desc in COMMANDS
    )
    await message.answer(help_text)


# Обработчик команды /me
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


# Добавляем глобальный архив критических задач
CriticalTasksArchive = []

# Новый обработчик для сбора сообщений с хэштегом "#Критичный" из чатов MONITOR_CHATS
@dp.message(lambda message: message.chat.id in list(map(int, config.target_chats)) and message.text and "#Критичный" in message.text)
async def monitor_critical_messages(message: types.Message):
    task = {
        "text": message.text,
        "link": f"https://t.me/c/{str(message.chat.id).replace('-100','')}/{message.message_id}",
        "date": message.date.strftime("%d.%m.%Y %H:%M"),
        "user_id": message.from_user.id if message.from_user else None,
        "username": message.from_user.username if message.from_user and message.from_user.username else None
    }
    CriticalTasksArchive.append(task)
    logger.info(f"Добавлена критическая задача из чата {message.chat.id}: {message.text[:30]}...")


# Функция для получения задач по тегу
async def get_tasks_by_tag(tag: str, user_id: int = None) -> List[str]:
    tasks = []
    for task in CriticalTasksArchive:
        if tag in task["text"]:
            if user_id is None or task.get("user_id") == user_id:
                tasks.append(task["text"])
    return tasks[:10]  # Возвращаем только первые 10 задач


# Изменяю функцию fetch_critical_tasks для возврата реальных задач из CriticalTasksArchive
async def fetch_critical_tasks(user_id: int = None) -> List[dict]:
    # Фильтруем задачи по user_id, если он указан
    filtered_tasks = CriticalTasksArchive
    if user_id is not None:
        filtered_tasks = [task for task in CriticalTasksArchive if task.get("user_id") == user_id]
    
    # Сортируем задачи по дате в обратном порядке и берем последние 10
    sorted_tasks = sorted(filtered_tasks, key=lambda x: datetime.datetime.strptime(x['date'], "%d.%m.%Y %H:%M"), reverse=True)[:10]
    return sorted_tasks


# Новая функция для выборки блокирующих задач с тегом #Блокер
async def fetch_blocker_tasks(user_id: int = None) -> List[dict]:
    # Фильтруем задачи по тегу и user_id, если он указан
    filtered_tasks = [task for task in CriticalTasksArchive if "#Блокер" in task['text']]
    if user_id is not None:
        filtered_tasks = [task for task in filtered_tasks if task.get("user_id") == user_id]
    
    sorted_tasks = sorted(filtered_tasks, key=lambda x: datetime.datetime.strptime(x['date'], "%d.%m.%Y %H:%M"), reverse=True)[:10]
    return sorted_tasks


# Новая функция для выборки релизных задач с тегами ['#Релиз', '#Приемка', '#Быстрый_Тест']
async def fetch_release_tasks(user_id: int = None) -> List[dict]:
    release_tags = ["#Релиз", "#Приемка", "#Быстрый_Тест"]
    # Фильтруем задачи по тегам
    filtered_tasks = [task for task in CriticalTasksArchive if any(tag in task['text'] for tag in release_tags)]
    # Дополнительно фильтруем по user_id, если он указан
    if user_id is not None:
        filtered_tasks = [task for task in filtered_tasks if task.get("user_id") == user_id]
    
    sorted_tasks = sorted(filtered_tasks, key=lambda x: datetime.datetime.strptime(x['date'], "%d.%m.%Y %H:%M"), reverse=True)[:10]
    return sorted_tasks


# Обработчик команды /crittask
@dp.message(Command("crittask"))
async def cmd_critical_tasks(message: types.Message):
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        # Получаем задачи только для текущего пользователя
        user_id = message.from_user.id if message.from_user else None
        tasks = await fetch_critical_tasks(user_id)
        
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
        logger.error(f"Ошибка в cmd_critical_tasks: {e}")
        await message.answer("⚠️ Произошла ошибка при получении критических задач!")


# Обработчик команды /task
@dp.message(Command("task"))
async def cmd_all_tasks(message: types.Message):
    try:
        user_id = message.from_user.id if message.from_user else None
        tasks = await get_tasks_by_tag("#ВсеЗадачи", user_id)
        
        if not tasks:
            await message.answer("📋 У вас нет активных задач")
            return
            
        response = "📋 <b>Все ваши задачи:</b>\n" + "\n".join(f"• {task[:150]}..." for task in tasks)
        await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка в cmd_all_tasks: {e}")
        await message.answer("⚠️ Произошла ошибка при получении задач!")


# Изменяю обработчик команды /releasetask
@dp.message(Command("releasetask"))
async def cmd_release_tasks(message: types.Message):
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        # Получаем задачи только для текущего пользователя
        user_id = message.from_user.id if message.from_user else None
        tasks = await fetch_release_tasks(user_id)
        
        if not tasks:
            await message.answer("📦 Нет активных релизных задач")
            return

        builder = InlineKeyboardBuilder()
        response = ["🚀 <b>Релизные задачи:</b>\n"]
        for idx, task in enumerate(tasks, 1):
            response.append(
                f"{idx}. <b>Задача {idx}</b>\n"
                f"📅 {task['date']}\n"
                f"📝 {task['text'][:150]}..."
            )
            builder.button(text=f"Задача {idx}", url=task['link'])

        builder.adjust(2)
        await message.answer(
            "\n".join(response),
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка в cmd_release_tasks: {e}")
        await message.answer("⚠️ Произошла ошибка при получении релизных задач!")


# Новые команды для расширения функционала

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not message.from_user or (message.from_user.username or "").lower() != "wildskjegg":
        await message.answer("У вас нет прав доступа к этой команде.")
        return
    await message.answer("Добро пожаловать в панель администратора. Функционал в разработке.")

@dp.message(Command("reminder"))
async def cmd_reminder(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Пожалуйста, укажите время в минутах от 1 до 60. Пример: /reminder 10")
            return
        try:
            minutes = int(parts[1])
        except ValueError:
            await message.answer("Неверный формат времени. Укажите целое число минут от 1 до 60.")
            return

        if minutes < 1 or minutes > 60:
            await message.answer("Время должно быть в диапазоне от 1 до 60 минут.")
            return

        # Сохраняем ID пользователя и чата для отправки напоминания
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        await message.answer(f"Напоминание установлено. Я напомню через {minutes} минут(ы).")

        async def send_reminder():
            import asyncio
            await asyncio.sleep(minutes * 60)
            try:
                # Отправляем напоминание в тот же чат и тому же пользователю
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"<b>@{message.from_user.username}</b>, не забудь проверить задачи/дашборд/доску",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания: {e}")

        import asyncio
        asyncio.create_task(send_reminder())
    except Exception as e:
        logger.error(f"Ошибка в cmd_reminder: {e}")
        await message.answer("⚠️ Произошла ошибка при установке напоминания!")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not message.from_user or (message.from_user.username or "").lower() != "wildskjegg":
        await message.answer("У вас нет прав доступа к этой команде.")
        return
    await message.answer("Аналитика задач будет доступна в ближайшем обновлении. (Функционал в разработке)")

@dp.message(Command("external"))
async def cmd_external(message: types.Message):
    if not message.from_user or (message.from_user.username or "").lower() != "wildskjegg":
        await message.answer("У вас нет прав доступа к этой команде.")
        return
    await message.answer("Интеграция с внешними сервисами (например Jira, Trello) в разработке.")

@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    if not message.from_user or (message.from_user.username or "").lower() != "wildskjegg":
        await message.answer("У вас нет прав доступа к этой команде.")
        return
    await message.answer("Настройки пользователя: функционал в разработке.")

@dp.message(Command("bloker"))
async def cmd_bloker(message: types.Message):
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        # Получаем задачи только для текущего пользователя
        user_id = message.from_user.id if message.from_user else None
        tasks = await fetch_blocker_tasks(user_id)
        
        if not tasks:
            await message.answer("✅ Активных блокирующих задач не найдено!")
            return

        builder = InlineKeyboardBuilder()
        response = ["🚨 <b>Блокирующие задачи:</b>\n"]
        for idx, task in enumerate(tasks, 1):
            response.append(
                f"{idx}. <b>Задача {idx}</b>\n"
                f"📅 {task['date']}\n"
                f"📝 {task['text'][:150]}..."
            )
            builder.button(text=f"Задача {idx}", url=task['link'])

        builder.adjust(2)
        await message.answer(
            "\n".join(response),
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Ошибка в cmd_bloker: {e}")
        await message.answer("⚠️ Произошла ошибка при получении блокирующих задач!")

async def inline_query_handler(inline_query: types.InlineQuery):
    article = types.InlineQueryResultArticle(
        id='1',
        title='Пример ответа',
        input_message_content=types.InputTextMessageContent('Пример ответа')
    )
    await inline_query.answer([article], cache_time=1)

# Регистрирую inline query обработчик вручную
dp.inline_query.register(inline_query_handler)

# Глобальный обработчик ошибок
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    try:
        if isinstance(exception, TelegramBadRequest):
            logger.warning(f"Ошибка Telegram API: {exception}")
        else:
            logger.error(f"Необработанная ошибка: {exception}", exc_info=True)
        
        # Пытаемся отправить сообщение об ошибке администратору
        if update.message:
            chat_id = update.message.chat.id
            await bot.send_message(
                chat_id=chat_id,
                text="Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}", exc_info=True)
    return True


# Основная функция запуска бота
async def main():
    try:
        await bot.set_my_commands([types.BotCommand(command=cmd, description=desc) for cmd, desc in COMMANDS])
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 