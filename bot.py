from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackQueryHandler
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import logging
import json
import asyncio
import os
import re
from pathlib import Path
from typing import Dict, Any, Tuple

from dotenv import load_dotenv
import sys
# ЗАМЕНА: Используем асинхронный httpx вместо блокирующего requests
import httpx

# Загрузка переменных окружения из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Проверяем наличие всех нужных переменных
missing = []
if not BOT_TOKEN:
    missing.append("BOT_TOKEN")
if not ADMIN_CHAT_ID:
    missing.append("ADMIN_CHAT_ID")
if not GEMINI_API_KEY:
    missing.append("GEMINI_API_KEY")

if missing:
    print(f"❌ Ошибка: отсутствуют переменные среды: {', '.join(missing)}")
    sys.exit(1)
else:
    print("✅ Все переменные среды загружены успешно.")

# --- ПРОВЕРКА ДОСТУПНОСТИ GEMINI API (Используем httpx для асинхронности) ---


async def check_gemini_availability():
    """Асинхронная проверка доступности API."""
    test_url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        # Используем httpx.AsyncClient для асинхронной проверки
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{test_url}?key={GEMINI_API_KEY}")
            if response.status_code == 200:
                print("✅ Gemini API доступен.")
            else:
                print(
                    f"⚠️ Gemini API ответил ошибкой: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при обращении к Gemini API: {e}")

# Инициализация и запуск проверки перед импортом Telegram, если не запущен event loop
if __name__ == '__main__':
    try:
        # Пытаемся запустить проверку асинхронно
        asyncio.run(check_gemini_availability())
    except Exception:
        # Если запущено внутри другого event loop (например, IDE), пропустим
        print("⚠️ Проверка доступности API пропущена, так как не удалось запустить asyncio.run().")


# Импорты Telegram после проверки переменных

# --- 1. НАСТРОЙКИ И КОНСТАНТЫ ---
try:
    # Используйте свой фактический ADMIN_CHAT_ID здесь
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
except (TypeError, ValueError):
    # Заглушка, если ID не задан в .env
    ADMIN_CHAT_ID = 123456789
    logging.warning(
        "ADMIN_CHAT_ID не задан или неверен. Используется заглушка.")

# URL теперь будет использоваться с добавлением ключа в конце
MODEL_NAME = "gemini-2.5-flash-lite"
GEMINI_API_BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
GEMINI_API_URL = f"{GEMINI_API_BASE_URL}?key={GEMINI_API_KEY}"

# Уровни разговора для ConversationHandler
SELECT_LANG, CONTENT_MENU, AI_CHAT = range(3)

# Карта для унификации обработки статического контента (Адрес, Подготовка)
STATIC_CONTENT_MAP = {
    'btn_addr': 'adr_info',
    'btn_prep': 'prep_info',
}

# --- НОВАЯ КОНСТАНТА ДЛЯ ПАПКИ С ИЗОБРАЖЕНИЯМИ ---
IMG_FOLDER = 'pct_inf'
# ---------------------------------------------------


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения выбранного языка пользователя
user_data: Dict[int, str] = {}

# --- 2. СТРУКТУРА ЛОКАЛИЗАЦИИ И КОНТЕНТ (MESSAGES) ---
MESSAGES = {
    'ru': {
        # --- Общие фразы ---
        'lang_select_prompt': 'Выберите язык / Tilni tanlang:',
        'start_button': 'Начать',
        'welcome_message': '👋Здравствуйте! \n Я бот-ассистент доктора. Здесь Вы можете получить информацию о приеме, подготовке к осмотру и обзор современных методов лечения проктологических заболеваний\n\n📍Важная информация:\n\n Все данные анонимны.',
        'start_menu_prompt': 'Выберите интересующий раздел: 👇',
        'back_to_menu': 'Вы вернулись в главное меню.',
        'ai_chat_exit': 'Вы вышли из режима вопросов по лазерным технологиям. Выберите раздел в меню.',
        'ai_chat_prompt_user': 'Вы можете задать вопросы по теме "Лазерные технологии в проктологии" ниже 👇.',
        'ai_loading_status': '⏳ ИИ обрабатывает ваш запрос...',
        'help_text': '🇷🇺: Я бот-помощник по проктологии и лазерным технологиям. Нажмите /start, чтобы начать диалог. \n🇺🇿: Men proktologiya va lazer texnologiyalari boʻyicha yordamchi botman. Muloqotni boshlash uchun /start buyrugʻini bosing.',
        'enforce_lang_text': 'Пожалуйста, выберите язык, нажав на кнопку (Русский или O\'zbek tili), чтобы продолжить.',

        # --- Кнопки главного меню (RU) ---
        'btn_addr': '⏱ Время приема и адрес',
        'btn_callback': '☎️ Заказать обратный звонок',
        'btn_prep': '📌 Подготовка к осмотру врача',
        'btn_laser': '✨ О лазерных технологиях в проктологии',
        'btn_exit_ai': '🔙 Главное меню',

        # --- Обратный звонок (RU) ---
        'callback_confirm_ru': '✅ Ваш запрос на обратный звонок принят! Мы свяжемся с вами в ближайшее время.',
        'callback_admin_notify_ru': '🔔 **НОВЫЙ ЗАПРОС НА ЗВОНОК**\nОт пользователя: {username} (ID: {user_id})\nТелефон: {phone_number}\nПожалуйста, свяжитесь с ним.',

        # --- Динамический контент (Будет загружен из файлов) ---
        'adr_info_ru_post': '',
        'prep_info_ru_post': '',
        'laser_info_ru_post': '',
        'prompt_main_ru': '',
    },
    'uz': {
        # --- Общие фразы ---
        'lang_select_prompt': 'Выберите язык / Tilni tanlang:',
        'start_button': 'Boshlash',
        'welcome_message': "Xush kelibsiz!\n Men shifokorning bot-yordamchisiman. Bu yerda Siz ish tartibimiz, ko'rikka tayyorgarlik va zamonaviy davolash usullari haqida ma'lumot olishingiz mumkin. \n\n 📍Muhim \n\n Barcha ma'lumotlar anonim.",
        'start_menu_prompt': 'Sizni qiziqtiriyotgan havolani tanlang: 👇',
        'back_to_menu': 'Siz asosiy menyuga qaytdingiz.',
        'ai_chat_exit': 'Siz lazer texnologiyalari boʻyicha savollar rejimdan chiqdingiz. Menyudan boʻlimni tanlang.',
        'ai_chat_prompt_user': '"Proktologiyada lazer texnologiyalari" mavzusi boʻyicha savollaringiz boʻlsa quyida yozishingiz mumkin 👇.',
        'ai_loading_status': '⏳ ...',
        'help_text': '🇷🇺: Я бот-помощник по проктологии и лазерным технологиям. Нажмите /start, чтобы начать диалог. \n🇺🇿: Men proktologiya va lazer texnologiyalari boʻyicha yordamchi botman. Muloqotni boshlash uchun /start buyrugʻini bosing.',
        'enforce_lang_text': 'Iltimos, davom etish uchun tugmani (Русский yoki O\'zbek tili) bosib tilni tanlang.',

        # --- Кнопки главного меню (UZ) ---
        'btn_addr': '⏱ Qabul vaqti va manzil',
        'btn_callback': '☎️ Qayta qo‘ng‘iroqni so‘rash',
        'btn_prep': '📌 Doktor ko‘rigiga tayyorgarlik',
        'btn_laser': '✨ Proktologiyada lazer texnologiyalari (Ai)',
        'btn_exit_ai': '🔙 Asosiy menyu',

        # --- Обратный звонок (UZ) ---
        'callback_confirm_uz': '✅ Qayta qoʻngʻiroq soʻrovingiz qabul qilindi! Yaqin orada siz bilan bogʻlanamiz.',
        'callback_admin_notify_uz': '🔔 **YANGI QO‘NG‘IROQ SO‘ROVI**\nFoydalanuvchidan: {username} (ID: {user_id})\nTelefon: {phone_number}\nIltimos, u bilan bogʻlaning.',

        # --- Динамический контент (Будет загружен из файлов) ---
        'adr_info_uz_post': '',
        'prep_info_uz_post': '',
        'laser_info_uz_post': '',
        'prompt_main_uz': '',
    }
}


def load_messages_from_files():
    """Читает контент из внешних .txt файлов и обновляет словарь MESSAGES, используя абсолютные пути относительно скрипта."""

    # Получаем абсолютный путь к директории, где находится этот скрипт
    base_dir = Path(__file__).parent if '__file__' in globals() else Path('.')
    INF_FOLDER = 'txt_inf'  # Имя папки с контентом

    file_map = {
        'ru': {
            'adr_info_ru_post': 'adr_info_ru.txt',
            'prep_info_ru_post': 'prep_info_ru.txt',
            'laser_info_ru_post': 'laser_info_ru.txt',
            'prompt_main_ru': 'prompt_main_ru.txt',
        },
        'uz': {
            'adr_info_uz_post': 'adr_info_uz.txt',
            'prep_info_uz_post': 'prep_info_uz.txt',
            'laser_info_uz_post': 'laser_info_uz.txt',
            'prompt_main_uz': 'prompt_main_uz.txt',
        }
    }

    for lang, mapping in file_map.items():
        for key, filename in mapping.items():

            # Строим полный путь: base_dir / txt_inf / filename
            full_path = base_dir / INF_FOLDER / filename

            try:
                # Чтение текста файла
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                MESSAGES[lang][key] = content
                logger.info(f"Successfully loaded {full_path}")
            except FileNotFoundError:
                # Используем os.path.normpath для очистки отображения пути в логе
                normalized_path = os.path.normpath(str(full_path))
                error_msg = f"❌ ОШИБКА: Файл '{normalized_path}' не найден. Проверьте, что папка '{INF_FOLDER}' находится рядом со скриптом и содержит файл '{filename}'."
                MESSAGES[lang][key] = error_msg
                logger.error(error_msg)
            except Exception as e:
                error_msg = f"❌ ОШИБКА при чтении файла '{full_path}': {e}"
                MESSAGES[lang][key] = error_msg
                logger.error(error_msg)


# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_text(user_id, key):
    """Возвращает текст на выбранном пользователем языке."""
    lang = user_data.get(user_id, 'ru')
    # Используем get() для безопасного доступа
    return MESSAGES.get(lang, MESSAGES['ru']).get(key, MESSAGES['ru'].get(key, f"❌ Ошибка: Ключ '{key}' не найден."))


def create_main_keyboard(user_id):
    """
    Создает клавиатуру главного меню с 4 кнопками на выбранном языке.
    Кнопка 'Обратный звонок' теперь запрашивает контакт.
    """
    callback_button_text = get_text(user_id, 'btn_callback')

    # Используем KeyboardButton с request_contact=True
    callback_button = KeyboardButton(
        callback_button_text, request_contact=True)

    return ReplyKeyboardMarkup(
        [
            [get_text(user_id, 'btn_addr')],
            [callback_button],
            [get_text(user_id, 'btn_prep')],
            [get_text(user_id, 'btn_laser')]
        ],
        resize_keyboard=True
    )


def create_ai_exit_keyboard(user_id):
    """
    Создает клавиатуру с единственной кнопкой для выхода из AI чата/раздела.
    """
    return ReplyKeyboardMarkup(
        [[get_text(user_id, 'btn_exit_ai')]],
        resize_keyboard=True
    )

# --- ИСПРАВЛЕННАЯ АСИНХРОННАЯ ФУНКЦИЯ ДЛЯ ВЫЗОВА API НА БАЗЕ HTTX (Теперь принимает историю) ---


async def call_gemini_api(system_prompt: str, history: list[dict[str, Any]]) -> str:
    """
    Асинхронно вызывает Gemini API для получения ответа, используя httpx
    с экспоненциальным отступом.

    ПРИМЕЧАНИЕ: Теперь принимает полную историю диалога (history) вместо user_query.
    """

    if "❌ ОШИБКА" in system_prompt:
        return f"Извините, ИИ не может работать, так как не удалось загрузить файл с инструкциями: {system_prompt}"

    # ПРАВИЛЬНАЯ СТРУКТУРА PAYLOAD (используем camelCase)
    payload: Dict[str, Any] = {
        # ИСПОЛЬЗУЕМ ПОЛНУЮ ИСТОРИЮ, ВКЛЮЧАЯ ПОСЛЕДНЕЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ
        "contents": history,

        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        # ДОБАВЛЕН ИНСТРУМЕНТ GOOGLE SEARCH GROUNDING (googleSearch в camelCase)
        "tools": [
            {"googleSearch": {}}
        ],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 2048
        }
    }

    # Используем httpx.AsyncClient для асинхронного выполнения
    async with httpx.AsyncClient(timeout=20.0) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    GEMINI_API_URL,
                    headers={'Content-Type': 'application/json'},
                    json=payload
                )

                # Проверяем на ошибки HTTP, включая 400
                response.raise_for_status()
                result = response.json()

                # Безопасное извлечение текста
                text = (
                    result.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )

                if text:
                    return text
                else:
                    logger.error(f"Gemini response structure error: {result}")
                    # Если ИИ не смог сгенерировать текст (часто, если нарушены лимиты безопасности)
                    return "Извините, произошла ошибка при обработке запроса ИИ. Попробуйте перефразировать вопрос."

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_details = ""
                try:
                    error_details = e.response.json().get('error', {}).get('message', '')
                except:
                    pass

                logger.warning(
                    f"Gemini API request failed (Attempt {attempt + 1}): {e}. Details: {error_details}")

                if attempt < 2 and status_code in (429, 500, 503):
                    # Экспоненциальное отступление для временных ошибок
                    await asyncio.sleep(2 ** attempt)
                    continue

                if status_code in [400, 403]:
                    return f"⚠️ **Ошибка подключения к ИИ (Код {status_code})**. Проверьте, что ваш GEMINI_API_KEY активен или что структура запроса верна. Детали: {error_details}"

                return "Извините, не удалось связаться с ИИ. Попробуйте позже."

            except httpx.RequestError as e:
                logger.warning(
                    f"Gemini API request failed (Attempt {attempt + 1}, Connection Error): {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return "Извините, не удалось связаться с ИИ. Проверьте свое интернет-соединение."

    return "Извините, не удалось связаться с ИИ. Попробуйте позже."
# --- КОНЕЦ ИСПРАВЛЕННОЙ ФУНКЦИИ call_gemini_api ---


# --- 4. ФУНКЦИИ БОТА (ХЭНДЛЕРЫ) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/start: Запрос выбора языка (Inline Keyboard с флагами), кнопки расположены вертикально для лучшего центрирования."""

    # Разделяем кнопки на отдельные строки для визуального центрирования
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbek tili", callback_data='lang_uz')],
        [InlineKeyboardButton("🇷🇺 Русский язык", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target_message = update.message if update.message else update.callback_query.message

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=MESSAGES['ru']['lang_select_prompt'],
            reply_markup=reply_markup
        )
        await update.callback_query.answer()
    elif target_message:
        await target_message.reply_text(
            text=MESSAGES['ru']['lang_select_prompt'],
            reply_markup=reply_markup
        )

    return SELECT_LANG


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора языка.
    ОТПРАВКА 1: Изображение
    ОТПРАВКА 2: Приветственный текст
    ОТПРАВКА 3: Главное меню
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang_code = query.data.split('_')[1]

    user_data[user_id] = lang_code

    # Получаем необходимый контент
    welcome_text = get_text(user_id, 'welcome_message')
    menu_prompt = get_text(user_id, 'start_menu_prompt')

    # 1. 🖼️ ОПРЕДЕЛЕНИЕ ПУТИ И ОТПРАВКА ИЗОБРАЖЕНИЯ (ПЕРВЫЙ ШАГ)
    base_dir = Path(__file__).parent if '__file__' in globals() else Path('.')
    photo_filename = f'welcom_{lang_code}.jpg'
    photo_path = base_dir / IMG_FOLDER / photo_filename

    logger.info(f"Attempting to send photo from: {photo_path}")

    try:
        with open(photo_path, 'rb') as photo_file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_file,
                # В этом варианте мы не используем подпись, чтобы текст пришел отдельно
            )
        logger.info(f"Successfully sent welcome photo: {photo_filename}")
    except FileNotFoundError:
        logger.error(
            f"❌ ОШИБКА: Приветственный файл изображения не найден по пути: {photo_path}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Изображение **{photo_filename}** не найдено. Проверьте путь.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ ОШИБКА при отправке фото {photo_filename}: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Произошла ошибка при отправке изображения: {e}",
            parse_mode='Markdown'
        )

    # 2. 💬 ОТПРАВКА ПРИВЕТСТВЕННОГО ТЕКСТА (ВТОРОЙ ШАГ)
    # Отправляем welcome_message отдельным сообщением
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=welcome_text,
    )

    # 3. 🧹 РЕДАКТИРУЕМ СООБЩЕНИЕ С КНОПКАМИ ВЫБОРА ЯЗЫКА (Убираем его)
    # Редактируем *предыдущее* сообщение (с кнопками выбора языка)
    await query.edit_message_text(
        text="."  # Заменяем на точку или пустоту, чтобы убрать кнопки
    )

    # 4. ⌨️ ОТПРАВКА МЕНЮ (ТРЕТИЙ ШАГ)
    reply_markup = create_main_keyboard(user_id)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=menu_prompt,  # Текст-приглашение в меню
        reply_markup=reply_markup
    )

    return CONTENT_MENU  # <-- Переход сразу в CONTENT_MENU


async def contact_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    НОВЫЙ ХЕНДЛЕР: Обрабатывает сообщение, содержащее контактные данные 
    после нажатия кнопки 'Заказать обратный звонок'.
    """
    message = update.message
    user_id = message.from_user.id
    lang = user_data.get(user_id, 'ru')

    # Извлекаем данные о контакте и номере телефона
    contact = message.contact
    # Если contact существует, извлекаем phone_number. В идеале он всегда должен быть.
    phone_number = contact.phone_number if contact and contact.phone_number else "❌ НЕТ ДАННЫХ"

    # Получаем user info
    user = update.effective_user
    # Формируем информацию о пользователе: @username или Полное имя (без @), если нет
    username_info = f"@{user.username}" if user.username else f"{user.full_name} (без @)"

    # Формируем текст уведомления для админа (на русском)
    admin_notify_text = MESSAGES['ru']['callback_admin_notify_ru'].format(
        username=username_info,
        user_id=user.id,
        phone_number=phone_number
    )

    # Отправка уведомления администратору
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_notify_text,
            parse_mode='Markdown'
        )
        logger.info(
            f"Callback contact received and admin notification sent from user {user.id} with number {phone_number}")
    except Exception as e:
        logger.error(
            f"Failed to send admin notification to {ADMIN_CHAT_ID} with contact: {e}")
        # Если не удалось отправить админу, уведомим пользователя об ошибке
        await message.reply_text("Произошла ошибка при отправке запроса администратору. Пожалуйста, повторите попытку.")
        return CONTENT_MENU

    # Подтверждение пользователю (на его языке)
    await message.reply_text(
        get_text(user_id, f'callback_confirm_{lang}'),
        # Возвращаем основную клавиатуру
        reply_markup=create_main_keyboard(user_id)
    )

    return CONTENT_MENU


async def content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Общий обработчик для кнопок, выводящих только текст, или для перехода в AI_CHAT."""
    user_id = update.effective_user.id
    user_message_text = update.message.text
    lang = user_data.get(user_id, 'ru')

    main_keyboard = create_main_keyboard(user_id)
    # Клавиатура с одной кнопкой "🔙 Главное меню"
    ai_exit_keyboard = create_ai_exit_keyboard(user_id)

    # --- 1. Обработка статического контента (Адрес, Подготовка) ---
    for btn_key, content_prefix in STATIC_CONTENT_MAP.items():
        if user_message_text == get_text(user_id, btn_key):
            # Генерируем ключ контента: 'content_prefix' + '_info_' + 'lang' + '_post' = 'adr_info_ru_post'
            post_key = f'{content_prefix}_{lang}_post'
            response_text = get_text(user_id, post_key)

            # Проверка, чтобы избежать ошибки Markdown, если контент не загружен
            parse_mode = 'Markdown' if "❌ ОШИБКА" not in response_text else None

            await update.message.reply_markdown(
                response_text,
                reply_markup=ai_exit_keyboard  # Используем клавиатуру с кнопкой "Назад"
            )
            return CONTENT_MENU  # Остаемся в CONTENT_MENU, ожидая "Назад"

    # --- 2. ОБРАТНЫЙ ЗВОНОК
    if user_message_text == get_text(user_id, 'btn_callback'):
        # Пользователь нажал кнопку с текстом.
        await update.message.reply_text(
            "Чтобы отправить запрос, пожалуйста, нажмите кнопку **'Поделиться контактом'** (Share Contact), которая должна была появиться над клавиатурой.",
            parse_mode='Markdown'
        )
        return CONTENT_MENU

    # --- 3. ЛАЗЕРНЫЕ ТЕХНОЛОГИИ -> ВХОД В AI_CHAT
    elif user_message_text == get_text(user_id, 'btn_laser'):
        post_key = f'laser_info_{lang}_post'

        # ✅ НОВЫЙ КОД: ИНИЦИАЛИЗАЦИЯ ИСТОРИИ ДЛЯ ЧАТА
        # Обнуляем историю, чтобы новый сеанс начинался без старого контекста
        context.user_data['history'] = []

        # 1. Отправляем информационный текст (с меню 4 кнопок)
        await update.message.reply_markdown(
            get_text(user_id, post_key),
            reply_markup=main_keyboard
        )

        # 2. Отправляем сообщение-приглашение в чат (с кнопкой выхода)
        await update.message.reply_text(
            get_text(user_id, 'ai_chat_prompt_user'),
            reply_markup=create_ai_exit_keyboard(user_id)
        )
        return AI_CHAT

    # --- 4. Обработка кнопки "🔙 Главное меню" (В CONTENT_MENU) ---
    if user_message_text == get_text(user_id, 'btn_exit_ai'):
        # Эта ветка обрабатывает случай, когда кнопка "Назад" нажимается
        # при просмотре статического контента.
        return await exit_chat_to_menu(update, context)

    # На случай, если пользователь ввел произвольный текст в меню (CONTENT_MENU)
    await update.message.reply_text(
        get_text(user_id, 'start_menu_prompt'),
        reply_markup=main_keyboard
    )

    return CONTENT_MENU


async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка вопросов пользователя в режиме AI_CHAT."""
    user_id = update.effective_user.id
    user_query = update.message.text
    lang = user_data.get(user_id, 'ru')

    # Клавиатура для выхода должна оставаться
    ai_exit_keyboard = create_ai_exit_keyboard(user_id)

    # --- ЗАГРУЖЕННЫЙ СИСТЕМНЫЙ ПРОМПТ ---
    system_prompt = get_text(user_id, f'prompt_main_{lang}')

    # ✅ НОВЫЙ КОД: УПРАВЛЕНИЕ ИСТОРИЕЙ
    # Получаем текущую историю. Если по какой-то причине ее нет, инициализируем пустой список.
    history = context.user_data.get('history', [])

    # 1. Добавляем текущее сообщение пользователя в историю
    history.append({"role": "user", "parts": [{"text": user_query}]})

    # Отправляем сообщение-статус (Теперь зависит от языка)
    status_message_text = get_text(user_id, 'ai_loading_status')
    status_message = await update.message.reply_text(status_message_text, reply_markup=ai_exit_keyboard)

    # 2. АСИНХРОННЫЙ ВЫЗОВ с полной историей
    # Передаем system_prompt и history
    ai_response = await call_gemini_api(system_prompt, history)

    # Удаляем сообщение-статус
    try:
        await status_message.delete()
    except Exception as e:
        logger.warning(f"Could not delete status message: {e}")

    # 3. Если ответ успешен, добавляем ответ ИИ в историю
    if not ai_response.startswith(("Извините", "⚠️")):
        # Добавляем ответ ИИ в историю (роль 'model')
        history.append({"role": "model", "parts": [{"text": ai_response}]})

    # 4. Обновляем историю в контексте пользователя (даже если была ошибка, чтобы сохранить предыдущие шаги)
    context.user_data['history'] = history

    # Отправляем ответ ИИ
    await update.message.reply_text(ai_response, reply_markup=ai_exit_keyboard)

    return AI_CHAT


async def exit_chat_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Возврат из AI_CHAT или из статического контента в CONTENT_MENU по кнопке "🔙 Главное меню".
    Используется универсальное сообщение 'back_to_menu'.
    """
    user_id = update.effective_user.id

    # Генерируем клавиатуру главного меню
    reply_markup = create_main_keyboard(user_id)

    # Отправляем сообщение с клавиатурой
    await update.message.reply_text(
        get_text(user_id, 'back_to_menu'),
        reply_markup=reply_markup
    )

    return CONTENT_MENU

# --- НОВЫЕ ХЭНДЛЕРЫ ДЛЯ УСТРАНЕНИЯ ОШИБОК IDE ---


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /help, возвращающий состояние выбора языка, если вызван там."""
    user_id = update.effective_user.id

    # Отправляем сообщение помощи (текст уже добавлен в MESSAGES)
    await update.message.reply_text(get_text(user_id, 'help_text'))

    # help_command возвращает то же состояние, в котором он был вызван.
    # Так как ConversationHandler ловит его в трех разных состояниях, нам нужно
    # вернуть состояние, которое, вероятно, будет следующим:
    # После /help в SELECT_LANG, пользователь должен вернуться к SELECT_LANG.
    if context.in_state == SELECT_LANG:
        return SELECT_LANG
    elif context.in_state == AI_CHAT:
        return AI_CHAT
    else:
        return CONTENT_MENU


async def enforce_lang_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик, который ловит некомандные сообщения в состоянии SELECT_LANG 
    и напоминает пользователю о необходимости выбора языка.
    """
    if update.message:
        await update.message.reply_text(get_text(update.effective_user.id, 'enforce_lang_text'))

    # Всегда остаемся в состоянии SELECT_LANG, пока не будет нажата кнопка.
    return SELECT_LANG

# --- 5. НАСТРОЙКА БОТА (Application) ---


def main() -> None:
    """Запуск бота."""

    if not BOT_TOKEN:
        logger.error(
            "BOT_TOKEN не найден в переменных окружения. Бот не запустится.")
        return

    # ВАЖНО: Загружаем контент из файлов перед запуском бота
    load_messages_from_files()

    # Создаем регулярное выражение для кнопки выхода из AI, чтобы ловить ее на любом языке
    RU_EXIT = re.escape(MESSAGES['ru']['btn_exit_ai'])
    UZ_EXIT = re.escape(MESSAGES['uz']['btn_exit_ai'])
    # Ловит оба варианта, либо с начала до конца строки
    EXIT_AI_REGEX = f"^{RU_EXIT}|{UZ_EXIT}$"

    # Создаем регулярное выражение для всех кнопок главного меню
    RU_BUTTONS = [MESSAGES['ru'][k]
                  for k in ['btn_addr', 'btn_callback', 'btn_prep', 'btn_laser']]
    UZ_BUTTONS = [MESSAGES['uz'][k]
                  for k in ['btn_addr', 'btn_callback', 'btn_prep', 'btn_laser']]

    # Экранируем все символы в названиях кнопок и объединяем их через '|'
    ALL_MENU_BUTTONS_REGEX = "^(" + "|".join(re.escape(b)
                                             for b in RU_BUTTONS + UZ_BUTTONS) + ")$"

    logger.info("Starting Telegram Bot Application...")

    application = Application.builder().token(BOT_TOKEN).build()

    # --- ИСПРАВЛЕНИЕ: Правильное определение ConversationHandler ---
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],

        states={
            # ИСПРАВЛЕНО: help_command возвращает SELECT_LANG, если вызван здесь.
            SELECT_LANG: [
                CommandHandler("start", start),
                CommandHandler("help", help_command),
                CallbackQueryHandler(select_language, pattern='^lang_'),
                MessageHandler(filters.ALL & ~filters.COMMAND,
                               enforce_lang_selection),
            ],

            CONTENT_MENU: [
                # Обрабатывает отправку контакта после нажатия "Обратный звонок"
                MessageHandler(filters.CONTACT, contact_message_handler),

                # Ловит нажатие кнопки "🔙 Главное меню" (выход из статического контента)
                MessageHandler(filters.Regex(EXIT_AI_REGEX) &
                               filters.TEXT, exit_chat_to_menu),

                # Главный обработчик 4-х кнопок (Адрес, Звонок, Подготовка, Лазер)
                MessageHandler(filters.Regex(ALL_MENU_BUTTONS_REGEX)
                               & filters.TEXT, content_handler),

                # Если введен произвольный текст в меню, он возвращает в меню, чтобы ждать выбора кнопки
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               content_handler),
                CommandHandler("start", start),
                CommandHandler("help", help_command),
            ],

            AI_CHAT: [
                # Ловит нажатие кнопки "🔙 Главное меню" (выход из AI чата)
                MessageHandler(filters.Regex(EXIT_AI_REGEX) &
                               filters.TEXT, exit_chat_to_menu),
                CommandHandler("start", start),  # /start тоже выводит из чата
                CommandHandler("help", help_command),
                # Все остальное в AI_CHAT - это запрос к ИИ
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               ai_chat_handler),
            ]
        },

        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("help", help_command),
        ],
    )
    # --- КОНЕЦ ИСПРАВЛЕНИЯ: Теперь conv_handler определен ---

    application.add_handler(conv_handler)

    logger.info("Bot started and polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy())  # Windows fix
    main()
