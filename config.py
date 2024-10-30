import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Добавьте сообщения бота
WELCOME_MESSAGE = """
Привет! 👋 Я помогу вам сохранять контент из Telegram в Notion.

Для начала работы:
1. Подключите ваш аккаунт Notion
2. Выберите страницу для сохранения
"""

HELP_MESSAGE = """
🤖 Как пользоваться ботом:

1️⃣ Отправьте любой текст - первая строка станет заголовком страницы
2️⃣ Пересылайте посты из других каналов
3️⃣ Отправляйте фото и документы

Команды:
/change_page - Выбрать другую страницу
/help - Показать это сообщение
"""