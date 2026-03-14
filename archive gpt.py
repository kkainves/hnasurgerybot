import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
    constants  # Для ParseMode и ChatAction
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from openai import OpenAI
from openai import RateLimitError # Явно импортируем ошибку для лучшей обработки

# === Настройка логов ===
# Используем стандартный формат для логов в файл
logging.basicConfig(
    filename="gpt_queries.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
# Дополнительно выводим INFO в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# === Загружаем ключи ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    logging.critical("BOT_TOKEN или OPENAI_API_KEY не найдены в файле .env!")
    raise EnvironmentError("Необходимо настроить переменные окружения BOT_TOKEN и OPENAI_API_KEY.")

# Инициализация клиента OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# === Константы для истории чата ===
GPT_HISTORY_KEY = "gpt_history"
MAX_HISTORY_LENGTH = 10  # Максимальное количество сообщений (диалоговых пар) для сохранения контекста

# === Пути ===
TXT_PATH = "txt_inf"
IMG_PATH = "pct_inf/wlcm.jpg"
SYSTEM_PROMPT_PATH = os.path.join("prompt", "prompt_main.txt")
ADMIN_CHAT_ID = "@hnasurgery"  # Канал или ID администратора

# === Клавиатуры: Централизованное определение ===
def main_menu_keyboard():
    """Клавиатура главного меню."""
    keyboard = [
        ["📍 Узнать время приема и адрес"],
        ["🩺 Как подготовиться к осмотру врача"],
        ["📞 Заказать обратный звонок"],
        ["💡 Лазерные технологии в проктологии"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_button_keyboard():
    """Клавиатура с кнопкой 'Возврат в главное меню'."""
    return ReplyKeyboardMarkup([["🔙 Возврат в главное меню"]], resize_keyboard=True)

def callback_request_keyboard():
    """Клавиатура для запроса номера телефона."""
    contact_button = KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    return ReplyKeyboardMarkup([[contact_button], ["🔙 Возврат в главное меню"]], resize_keyboard=True)

# === Хелпер: Очистка истории ===
def reset_chat_history(context: ContextTypes.DEFAULT_TYPE):
    """Очищает историю диалога пользователя в контексте."""
    if GPT_HISTORY_KEY in context.user_data:
        context.user_data[GPT_HISTORY_KEY] = []
        logging.info(f"Chat history reset.")

# === Приветствие ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение, главное меню и сбрасывает историю."""
    reset_chat_history(context)
    try:
        with open(IMG_PATH, "rb") as img:
            await update.message.reply_photo(
                photo=InputFile(img),
                caption=(
                    "Вы находитесь на странице врача-проктолога, хирурга высшей категории, "
                    "к.м.н. Ходжимухамедовой Нигоры Абдукамаловны.\n\n"
                    "Здесь Вы можете узнать информацию о приёме врача и задать вопросы."
                ),
                reply_markup=main_menu_keyboard()
            )
    except FileNotFoundError:
        logging.error(f"Файл изображения не найден: {IMG_PATH}")
        await update.message.reply_text("Приветствие! Не удалось загрузить фото.", reply_markup=main_menu_keyboard())


# === Кнопка 1: Адрес ===
async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает запрос адреса и времени приема."""
    reset_chat_history(context)
    try:
        with open(os.path.join(TXT_PATH, "adr_info.txt"), "r", encoding="utf-8") as f:
            await update.message.reply_text(f.read(), reply_markup=back_button_keyboard())
    except FileNotFoundError:
        logging.error(f"Файл адреса не найден: {os.path.join(TXT_PATH, 'adr_info.txt')}")
        await update.message.reply_text("Информация об адресе временно недоступна.", reply_markup=back_button_keyboard())

# === Кнопка 2: Запрос обратного звонка ===
async def handle_callback_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает номер телефона для обратного звонка."""
    reset_chat_history(context)
    await update.message.reply_text(
        "📞 Пожалуйста, отправьте свой номер телефона, чтобы мы могли вам перезвонить:",
        reply_markup=callback_request_keyboard()
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет номер телефона администратору и благодарит пользователя."""
    contact = update.message.contact
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"📞 Запрос на звонок от пользователя {update.effective_user.id}. Номер: {contact.phone_number}"
    )
    await update.message.reply_text(
        "✅ Ваш запрос принят. Наш специалист свяжется с вами в ближайшее время.",
        reply_markup=main_menu_keyboard()
    )

# === Кнопка 3: Подготовка к осмотру ===
async def handle_visit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает запрос информации о подготовке к осмотру."""
    reset_chat_history(context)
    try:
        with open(os.path.join(TXT_PATH, "vis_info.txt"), "r", encoding="utf-8") as f:
            await update.message.reply_text(f.read(), reply_markup=back_button_keyboard())
    except FileNotFoundError:
        logging.error(f"Файл vis_info не найден: {os.path.join(TXT_PATH, 'vis_info.txt')}")
        await update.message.reply_text("Информация о подготовке временно недоступна.", reply_markup=back_button_keyboard())

# === Кнопка 4: Лазерные технологии (измененный поток) ===
async def handle_laser_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет информацию о лазерных технологиях.
    После этого пользователь может сразу начать диалог с GPT.
    """
    # Сброс истории чата, чтобы начать новый диалог
    reset_chat_history(context)
    
    try:
        with open(os.path.join(TXT_PATH, "laser_info.txt"), "r", encoding="utf-8") as f:
            text = f.read()
            
        # Добавляем призыв к действию, как просили
        full_text = f"{text}\n\n**Вы можете задать вопрос ниже.**"
        
        await update.message.reply_text(
            full_text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=back_button_keyboard() # Оставляем только "Возврат"
        )
            
    except FileNotFoundError:
        logging.error(f"Файл laser_info не найден: {os.path.join(TXT_PATH, 'laser_info.txt')}")
        await update.message.reply_text("Информация о лазере временно недоступна.", reply_markup=back_button_keyboard())


# === GPT-вопрос (С памятью) ===
async def handle_gpt_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает текстовые вопросы пользователя с использованием GPT-4o-mini, 
    поддерживая историю диалога (контекст).
    """
    user_message = update.message.text
    
    # 0. Инициализация или получение истории
    chat_history = context.user_data.get(GPT_HISTORY_KEY, [])
    
    # 1. Отправляем стандартный индикатор "печатает"
    await context.bot.send_chat_action(update.effective_chat.id, constants.ChatAction.TYPING)

    # 2. Отправляем пользователю уведомление об ожидании
    # Важно: это сообщение мы будем удалять, а не редактировать, чтобы избежать ошибок Telegram.
    wait_message = await update.message.reply_text("💭 Идет подготовка ответа...")
    
    answer = None
    user_error_text = None

    try:
        # Чтение system_prompt (делается при каждом вызове для надежности)
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read()

        # 3. Формирование списка сообщений для API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем существующую историю
        messages.extend(chat_history)
        
        # Добавляем текущее сообщение пользователя и обновляем локальную историю
        messages.append({"role": "user", "content": user_message})
        chat_history.append({"role": "user", "content": user_message})
        
        # Запрос к GPT
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        answer = response.choices[0].message.content.strip()
        
        # 4. Обновляем историю с ответом GPT
        chat_history.append({"role": "assistant", "content": answer})
        
        # 5. Ограничиваем историю, чтобы не превышать лимиты токенов
        # Сохраняем только последние MAX_HISTORY_LENGTH пар сообщений
        if len(chat_history) > MAX_HISTORY_LENGTH * 2:
            context.user_data[GPT_HISTORY_KEY] = chat_history[-(MAX_HISTORY_LENGTH * 2):]
        else:
            context.user_data[GPT_HISTORY_KEY] = chat_history


        logging.info(f"{datetime.now()} - USER: {update.effective_user.id} | MSG: {user_message} | GPT: {answer}")

    except FileNotFoundError:
        logging.error(f"Файл prompt не найден: {SYSTEM_PROMPT_PATH}")
        user_error_text = "⚠️ Ошибка: Файл с инструкцией для ИИ не найден."
        
    except RateLimitError as e:
        # Перехватываем конкретно ошибку квоты
        logging.error(f"Ошибка RateLimit (квота): {e}")
        user_error_text = "🚫 **Ошибка квоты API:** Извините, но кажется, закончился лимит для обращения к искусственному интеллекту. Попробуйте позже или обратитесь к администратору."
        
    except Exception as e:
        # Обработка всех остальных ошибок (например, сетевых)
        logging.error(f"Общая ошибка при вызове OpenAI: {e}")
        user_error_text = "⚠️ Внутренняя ошибка при обращении к GPT. Попробуйте позже."


    # 6. Финализация: Удаляем сообщение ожидания и отправляем окончательный результат
    try:
        # Удаляем сообщение ожидания (даже если была ошибка)
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=wait_message.message_id
        )
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение ожидания: {e}")
        # Если не удалось удалить, просто продолжаем

    if answer:
        # Если ответ получен успешно
        final_text = f"💬 {answer}\n\n_Ответ сформирован с использованием ИИ._"
    else:
        # Если произошла ошибка (user_error_text был установлен)
        final_text = user_error_text

    await update.message.reply_text(
        text=final_text,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=back_button_keyboard()
    )


# === Возврат ===
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню и очистка истории чата."""
    reset_chat_history(context)
    await update.message.reply_text("🔝 Главное меню:", reply_markup=main_menu_keyboard())

# === Запуск ===
def main():
    """Настройка и запуск бота."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    
    # Обработчики главного меню (Фильтруем по началу текста, чтобы не конфликтовать с GPT)
    app.add_handler(MessageHandler(filters.Regex("^📍"), handle_address))
    app.add_handler(MessageHandler(filters.Regex("^📞"), handle_callback_request))
    app.add_handler(MessageHandler(filters.Regex("^🩺"), handle_visit_info))
    app.add_handler(MessageHandler(filters.Regex("^💡"), handle_laser_info))
    
    # Обработчик контакта
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    
    # Обработчик возврата в меню
    app.add_handler(MessageHandler(filters.Regex("🔙 Возврат в главное меню"), back_to_menu))
    
    # Обработчик GPT-вопроса: обрабатывает весь оставшийся текст, который не является командой или кнопкой
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gpt_question))


    logging.info("Бот запущен. Ожидание сообщений...")
    app.run_polling(poll_interval=1.0)

if __name__ == "__main__":
    main()