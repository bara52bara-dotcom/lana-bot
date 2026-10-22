import os
import json
import asyncio
import threading
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Автоматический ключ из настроек Render
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Инструкция заставляет ИИ возвращать и разбор, и чистое английское слово отдельно для таймера
PROMPT_TEMPLATE = """Ты — универсальный ИИ-ассистент по английскому языку. Студент прислал: "{word}".
1. Если текст на русском или это кривое произношение/суржик — пойми, какое ОДНО точное английское слово или устойчивую фразу он имел в виду.
2. Сделай разбор этого английского слова на ЛЮБЫЕ жизненные темы.

Ты ДОЛЖЕН ответить строго в формате JSON с двумя ключами:
"english_word": здесь напиши только чистое найденное английское слово (например: "inconsistency") для нашей базы повторения.
"analysis": здесь напиши разбор строго по пунктам:
1. 💡 Правильное слово на английском, транскрипция и перевод.
2. ❌ В чем была сложность (ошибка или произношение).
3. 🔬 Живой контекст: 2 сочных примера из реальной жизни на любые темы.
4. 🧠 Задание на активацию: 1 жизненный вопрос, чтобы студент ответил на него с этим словом.

Отвечай только чистым JSON, без лишних слов."""

async def send_spaced_repetition_push(chat_id, target_word):
    delay = 43200  # 12 часов
    print(f"[Таймер] Запущен для Chat ID {chat_id} на английское слово: {target_word}")
    await asyncio.sleep(delay)
    # Бот пришлет пуш именно с правильным английским словом!
    print(f"[ПУШ-УВЕДОМЛЕНИЕ] Отправлено пользователю {chat_id}: Ну что, повторим слово {target_word}?")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    incoming_word = data.get('word', '')
    chat_id = data.get('chat_id', '')
    
    if not incoming_word:
        return jsonify({"status": "error", "message": "No word provided"}), 400

    print(f"[Система] Получен запрос: {incoming_word}")

    # Запрос к ChatGPT с требованием JSON формата
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(word=incoming_word)}]
    )
    
    # Парсим ответ от ИИ
    result_json = json.loads(response.choices.message.content)
    ai_answer = result_json.get("analysis", "")
    detected_english_word = result_json.get("english_word", incoming_word)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    # ПУШ СРАБОТАЕТ НА ИСПРАВЛЕННОЕ АНГЛИЙСКОЕ СЛОВО
    loop.create_task(send_spaced_repetition_push(chat_id, detected_english_word))

    return jsonify({"status": "success", "reply_text": ai_answer})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
