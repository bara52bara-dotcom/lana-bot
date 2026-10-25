import os
import json
import asyncio
from flask import Flask, request, jsonify
from openai import OpenAI
import requests

app = Flask(__name__)

# Берем ключи из настроек Render
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

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

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=20
    )
    response.raise_for_status()

async def send_spaced_repetition_push(chat_id, target_word):
    delay = 43200  # 12 часов
    print(f"[Таймер] Запущен для Chat ID {chat_id} на слово: {target_word}")
    await asyncio.sleep(delay)
    send_telegram_message(chat_id, f"🔔 Интервальное повторение!\nНу что, давай закрепим в памяти слово: {target_word}?\nСоставь с ним новое предложение!")

@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or "message" not in data:
        return jsonify({"status": "ok"})
        
    message = data["message"]
    chat_id = message["chat_id"]["id"] if isinstance(message.get("chat_id"), dict) else message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    
    if not text or not chat_id:
        return jsonify({"status": "ok"})

    # Если человек только зашел или нажал Старт
    if text.lower() == "/start":
        welcome_text = "Привет! Я Лана, твой личный ИИ-тренажер для раскачки английского и уничтожения речевых блоков.\n\nНапиши или наговори сюда фразу/слово, в котором ты сомневаешься, и я разберу его по косточкам!"
        send_telegram_message(chat_id, welcome_text)
        return jsonify({"status": "ok"})

    print(f"[Сервер] Получено слово: {text} от ChatID: {chat_id}")
    send_telegram_message(chat_id, "⏳ Магия ИИ началась... Минутку, создаю твой персональный разбор...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(word=text)}]
        )
        result_json = json.loads(response.choices[0].message.content)
        ai_answer = result_json.get("analysis", "Не удалось сгенерировать разбор.")
        detected_english_word = result_json.get("english_word", text)

        # Отправляем разбор мгновенно
        send_telegram_message(chat_id, ai_answer)

        # Запускаем вечный таймер пуша на исправленное английское слово
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(send_spaced_repetition_push(chat_id, detected_english_word))

    except Exception as e:
        print(f"Ошибка: {e}")
        send_telegram_message(chat_id, "Ой, что-то пошло не так при общении с ИИ. Попробуй еще раз!")

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
