import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import ReplyKeyboardMarkup
from telegram.constants import ParseMode

# Загружаем переменные окружения из .env
load_dotenv()

# Используем переменные
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
API_KEY = os.getenv('API_KEY')

print(f"Токен: {TELEGRAM_TOKEN}")

# Команды для меню
COMMANDS = [
    ("start", "Начать работу с ботом"),
    ("help", "Показать меню команд"),
    ("info", "Информация о боте"),
    ("me", "Информация о пользователе")
]

# Обработчик команды /start
async def start(update: Update, context):
    # Создаем клавиатуру с командами
    keyboard = [['/start', '/help'], ['/info', '/me']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        'Привет! Я простой бот. Вот доступные команды:',
        reply_markup=reply_markup
    )

# Обработчик команды /help
async def help_command(update: Update, context):
    help_text = "<b>Доступные команды:</b>\n\n"
    help_text += "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS)
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

# Обработчик команды /info
async def info(update: Update, context):
    info_text = """
🚀 <b>Я бот для Yandex Tracker</b>
✅ Готов к работе в любое время!
"""
    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)

# Обработчик команды /me
async def me(update: Update, context):
    user = update.message.from_user
    user_info = f"""
<b>Информация о вас:</b>
🆔 ID: <code>{user.id}</code>
👤 Имя: {user.first_name}
👥 Фамилия: {user.last_name or 'не указана'}
📛 Username: @{user.username or 'не указан'}
🌐 Язык: {user.language_code or 'не указан'}
"""
    await update.message.reply_text(user_info, parse_mode=ParseMode.HTML)

# Установка меню команд
async def post_init(application):
    await application.bot.set_my_commands(COMMANDS)

# Основная функция
def main():
    # Вставьте сюда ваш токен
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("me", me))
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main() 