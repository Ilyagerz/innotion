import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler, filters
from notion_client import Client

# Структура для хранения выбранных страниц пользователей
user_pages = {}

class NotionTelegramBot:
    def __init__(self, telegram_token, notion_token):
        self.application = Application.builder().token(telegram_token).build()
        self.notion = Client(auth=notion_token)
        
        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("notion", self.notion_command))
        self.application.add_handler(CommandHandler("change_page", self.change_page))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))

    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        await update.message.reply_text(
            f"Привет, {user.first_name} 👋\n\n"
            "➡️ Для начала работы необходимо подключить ваш аккаунт Notion и выбрать страницу "
            "или базу данных, куда бот будет добавлять контент!\n\n"
            "Используйте команду /help для получения справки."
        )
        await self.show_page_selection(update, context)

    async def help(self, update: Update, context: CallbackContext):
        await update.message.reply_text(
            "🤖 IN-NOTION Bot позволяет отправлять контент из Telegram прямо в Notion.\n\n"
            "Вы можете отправлять:\n"
            "- Текстовые сообщения\n"
            "- Ссылки\n"
            "- Изображения\n"
            "- Пересылать посты из других каналов\n\n"
            "Команды:\n"
            "/change_page - Выбрать другую страницу Notion\n"
            "/notion [текст] - Отправить текст в Notion\n"
            "/help - Показать это сообщение"
        )

    async def show_page_selection(self, update: Update, context: CallbackContext):
        try:
            # Получаем список страниц пользователя
            pages = self.get_notion_pages()
            
            max_buttons_per_message = 10  # Максимальное количество кнопок на сообщение
            keyboard = []
            
            for i, page in enumerate(pages):
                # Проверяем наличие данных заголовка страницы
                title_property = page.get('properties', {}).get('title', {}).get('title', [])
                page_title = title_property[0].get('plain_text', 'Без названия') if title_property else 'Без названия'
                keyboard.append([InlineKeyboardButton(
                    f"{page_title[:20]} 📄",  # Ограничение на 20 символов
                    callback_data=f"page_{page['id']}"
                )])
                
                # Отправляем сообщения, если достигнуто максимальное количество кнопок
                if (i + 1) % max_buttons_per_message == 0:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "Выберите страницу для сохранения контента:",
                        reply_markup=reply_markup
                    )
                    keyboard = []  # Сбрасываем клавиатуру для следующего сообщения
            
            # Отправляем оставшиеся кнопки, если есть
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Выберите страницу для сохранения контента:",
                    reply_markup=reply_markup
                )
        except Exception as e:
            print(f"Ошибка при обработке списка страниц: {str(e)}")  # Добавьте вывод ошибки для отладки
            await update.message.reply_text(
                "Произошла ошибка при получении списка страниц. "
                "Пожалуйста, проверьте токен Notion и попробуйте снова."
            )

    async def button_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("page_"):
            page_id = query.data.replace("page_", "")
            user_pages[query.from_user.id] = page_id
            await query.edit_message_text(
                f"✅ Страница выбрана! Теперь вы можете отправлять контент, "
                f"и он будет сохраняться в выбранном месте."
            )

    async def handle_message(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in user_pages:
            await update.message.reply_text(
                "Пожалуйста, сначала выберите страницу Notion используя /change_page"
            )
            return

        text = update.message.text
        lines = text.split('\n')
        title = lines[0]
        content = '\n'.join(lines[1:]) if len(lines) > 1 else ""

        try:
            # Создаем страницу в Notion
            self.create_notion_page(
                user_pages[user_id],
                title,
                content
            )
            await update.message.reply_text("✅ Страница успешно создана в Notion!")
        except Exception as e:
            await update.message.reply_text(
                "Произошла ошибка при создании страницы. Пожалуйста, попробуйте снова."
            )

    async def handle_photo(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in user_pages:
            await update.message.reply_text(
                "Пожалуйста, сначала выберите страницу Notion используя /change_page"
            )
            return

        # Получаем файл фото
        photo = await update.message.photo[-1].get_file()
        
        try:
            # Создаем страницу с изображением
            caption = update.message.caption or "Изображение из Telegram"
            self.create_notion_page_with_image(
                user_pages[user_id],
                caption,
                photo.file_path
            )
            await update.message.reply_text("✅ Изображение сохранено в Notion!")
        except Exception as e:
            await update.message.reply_text(
                "Произошла ошибка при сохранении изображения. Пожалуйста, попробуйте снова."
            )

    async def change_page(self, update: Update, context: CallbackContext):
        await self.show_page_selection(update, context)

    async def notion_command(self, update: Update, context: CallbackContext):
        if not context.args:
            await update.message.reply_text(
                "Пожалуйста, добавьте текст после команды /notion, "
                "который вы хотите отправить в Notion."
            )
            return
        
        text = ' '.join(context.args)
        # Используем существующий обработчик сообщений
        update.message.text = text
        await self.handle_message(update, context)

    def get_notion_pages(self):
        """Получает список страниц пользователя"""
        try:
            response = self.notion.search(**{
                "filter": {
                    "value": "page",
                    "property": "object"
                }
            })
            print("Notion API Response:", response)  # Добавляем для отладки
            return response.get('results', [])
        except Exception as e:
            print(f"Ошибка при получении страниц Notion: {str(e)}")
            raise

    def create_notion_page(self, parent_id, title, content=""):
        """Создает новую страницу в Notion"""
        new_page = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": content
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        return self.notion.pages.create(**new_page)

    def create_notion_page_with_image(self, parent_id, caption, image_url):
        """Создает новую страницу с изображением в Notion"""
        new_page = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": caption
                            }
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {
                            "url": image_url
                        }
                    }
                }
            ]
        }
        
        return self.notion.pages.create(**new_page)

    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        self.application.run_polling()

# Запуск бота
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()  # загружаем переменные из .env файла
    
    # Получаем токены из переменных окружения
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    
    if not TELEGRAM_TOKEN or not NOTION_TOKEN:
        print("Ошибка: не найдены токены. Убедитесь, что установлены TELEGRAM_TOKEN и NOTION_TOKEN.")
    else:
        bot = NotionTelegramBot(TELEGRAM_TOKEN, NOTION_TOKEN)
        bot.run()
