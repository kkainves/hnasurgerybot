import os
from google import genai
from google.genai.errors import APIError

# === КОНТРОЛЬНАЯ ТОЧКА 1 ===
# Перенесено на первую строку для гарантированного вывода
print("--- Тестирование Gemini API начато ---") 

# ИМПОРТ ПЕРЕНЕСЕН СЮДА: Теперь, если здесь будет сбой, мы увидим хотя бы верхнее print()
from dotenv import load_dotenv

# Загружаем ключ из .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === КОНТРОЛЬНАЯ ТОЧКА 2: Проверка наличия ключа ===
print(f"Ключ API загружен: {bool(GEMINI_API_KEY)}")

if not GEMINI_API_KEY:
    print("Ошибка: GEMINI_API_KEY не найден в файле .env")
    print("Убедитесь, что .env находится в той же папке и содержит GEMINI_API_KEY=ВашКлюч")
    exit()

try:
    # === КОНТРОЛЬНАЯ ТОЧКА 3: Инициализация ===
    print("Попытка инициализации клиента Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    print("Отправка тестового запроса (Что такое проктология?)...")
    
    # Отправляем синхронный запрос
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Что такое проктология? Ответь кратко.",
        # Аргумент 'timeout' удален, так как он не поддерживается в этой версии SDK
    )
    
    # Выводим первые 200 символов ответа
    answer_snippet = response.text[:200].strip()
    
    print("\n✅ Успех! Ответ от Gemini получен.")
    print(f"Первые символы ответа: {answer_snippet}...")
    
except APIError as e:
    print("\n⚠️ Ошибка API. Ключ, вероятно, недействителен или превышена квота.")
    print(f"Детали ошибки: {e}")

except Exception as e:
    print("\n⚠️ Ошибка подключения (сеть, таймаут или другая проблема).")
    print(f"Детали ошибки: {e}")