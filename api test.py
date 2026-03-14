# -*- coding: utf-8 -*-
import asyncio
import httpx
import json
from typing import Dict, Any, Tuple

# --- КОНФИГУРАЦИЯ ---
# !!! ВАЖНО: ЗАМЕНИТЕ ЭТУ СТРОКУ НА ВАШ РЕАЛЬНЫЙ КЛЮЧ API !!!
API_KEY = "AIzaSyCo0kYucFZ9rmP3dyNN2HwCXE7orvb-38g"
MODEL_NAME = "gemini-2.5-flash-preview-09-2025"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

# --- ТЕСТИРУЕМЫЙ ЗАПРОС ---
TEST_SYSTEM_PROMPT = "Вы — бот-хирург. Дайте краткий совет по первой помощи (на русском языке)."
TEST_USER_QUERY = "Я порезал палец, что мне делать?"
# -----------------------------

async def call_gemini_api_async(system_prompt: str, user_query: str) -> Tuple[bool, str]:
    """
    Асинхронная функция для вызова API Gemini с использованием httpx.
    Реализован экспоненциальный откат (Exponential Backoff).
    """
    
    # Структура Payload: ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЕМ camelCase (systemInstruction, googleSearch)
    payload: Dict[str, Any] = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_query}]
            }
        ],
        # Добавляем Google Search для актуальности
        "tools": [{"googleSearch": {}}]
    }

    # Используем httpx.AsyncClient для асинхронного выполнения
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    GEMINI_API_URL,
                    headers={"Content-Type": "application/json"},
                    json=payload
                )

                # Проверка успешного статуса
                response.raise_for_status() 

                # Если запрос успешен (HTTP 200)
                result = response.json()
                text = (
                    result.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "⚠️ Ответ пуст или имеет неверную структуру.")
                )
                return True, text.strip()

            except httpx.HTTPStatusError as e:
                # Обработка HTTP-ошибок (например, 400 Bad Request)
                error_details = e.response.text
                print(f"  [Попытка {attempt + 1}] Ошибка HTTP {e.response.status_code}: {error_details}")
                if attempt < 2 and e.response.status_code in (429, 500, 503):
                    await asyncio.sleep(2 ** attempt)
                    continue
                return False, f"❌ Критическая ошибка API ({e.response.status_code}): {error_details}"

            except httpx.RequestError as e:
                # Обработка ошибок подключения/таймаута
                print(f"  [Попытка {attempt + 1}] Ошибка подключения: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return False, f"❌ Не удалось подключиться: {e}"
                
        return False, "❌ Все попытки вызова API завершились неудачей."


async def main():
    if API_KEY == "YOUR_API_KEY":
        print("!!! ОШИБКА КОНФИГУРАЦИИ !!!")
        print("Пожалуйста, замените 'YOUR_API_KEY' в коде на ваш ключ API.")
        return

    print(f"Тестирование асинхронного вызова API ({MODEL_NAME})...")
    success, message = await call_gemini_api_async(TEST_SYSTEM_PROMPT, TEST_USER_QUERY)
    
    print("-" * 50)
    if success:
        print("✅ УСПЕХ: Асинхронный вызов API прошел успешно.")
        print(f"Системный запрос (Persona): {TEST_SYSTEM_PROMPT}")
        print(f"Пользовательский запрос: {TEST_USER_QUERY}")
        print("-" * 50)
        print(f"Ответ ИИ:\n{message}")
    else:
        print("❌ СБОЙ: Асинхронный вызов API завершился неудачей.")
        print(f"Сообщение об ошибке:\n{message}")
    print("-" * 50)


if __name__ == "__main__":
    # Запускаем главную асинхронную функцию
    asyncio.run(main())