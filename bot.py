import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, time

from openai import AsyncOpenAI

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# States for ConversationHandler
ASK_TRIGGER, ASK_BEACON = range(2)

LOG_FILE = "log.json"

logging.basicConfig(level=logging.INFO)


def load_log():
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def append_log(entry):
    log = load_log()
    log.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


async def generate_tough_reply(trigger: str, leads: bool) -> str:
    """Generate a short tough-love reply using GPT."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Нет ключа GPT. Дыши сам."
    client = AsyncOpenAI(api_key=api_key)

    system_prompt = (
        "Ты — грубый поддерживающий наставник. Отвечай по-русски,"
        " коротко (2-3 предложения), с прямотой и лёгким стёбом."
    )
    if leads:
        user_prompt = (
            f"Пользователь сорвался на '{trigger}' и считает, что это ведёт к маяку."
            " Дай жёсткую поддержку и скажи двигаться по плану."
        )
    else:
        user_prompt = (
            f"Пользователь сорвался на '{trigger}', но это не ведёт к маяку."
            " Дай жёсткую поддержку и обязательно включи фразу 'Значит нахуй.'"
        )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=60,
            temperature=0.7,
        )
        reply = (response.choices[0].message.content or "").strip()
        if not leads and "Значит нахуй" not in reply:
            reply = "Значит нахуй. " + reply
        return reply
    except Exception as e:
        logging.error("OpenAI error: %s", e)
        return "Что-то пошло не так. Соберись сам."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send start message with main button and schedule reminders."""
    kb = ReplyKeyboardMarkup([["Я срываюсь"]], resize_keyboard=True)
    await update.message.reply_text("Жми, если понесло.", reply_markup=kb)

    # Daily reminders
    context.job_queue.run_daily(
        daily_check, time=time(hour=9), chat_id=update.effective_chat.id, name=str(update.effective_chat.id) + "_m"
    )
    context.job_queue.run_daily(
        daily_check, time=time(hour=21), chat_id=update.effective_chat.id, name=str(update.effective_chat.id) + "_e"
    )


async def daily_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        context.job.chat_id, "Ты держишь курс? Что сегодня сделал для маяка?"
    )


async def panic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Хуле ты опять ноешь? Что тебя ломает?", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_TRIGGER


async def handle_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["trigger"] = update.message.text
    kb = ReplyKeyboardMarkup([["Да", "Нет"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Ведёт к маяку?", reply_markup=kb)
    return ASK_BEACON


async def handle_beacon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.lower()
    trigger = context.user_data.get("trigger", "")
    leads = answer.startswith("д")

    reply = await generate_tough_reply(trigger, leads)
    await update.message.reply_text(
        reply,
        reply_markup=ReplyKeyboardMarkup([["Я срываюсь"]], resize_keyboard=True),
    )
    if not leads:
        context.job_queue.run_once(five_min_check, when=300, chat_id=update.effective_chat.id)

    append_log(
        {
            "time": datetime.now().isoformat(),
            "trigger": trigger,
            "leads_to_beacon": leads,
        }
    )
    return ConversationHandler.END


async def five_min_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(context.job.chat_id, "5 минут прошло. Всё ещё хочешь?")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log = load_log()
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    week_count = sum(
        1 for entry in log if datetime.fromisoformat(entry["time"]) >= week_ago
    )
    await update.message.reply_text(f"За неделю срывов: {week_count}")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var missing")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Я срываюсь$"), panic_entry)],
        states={
            ASK_TRIGGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger)],
            ASK_BEACON: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_beacon)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(conv)

    app.run_polling()


if __name__ == "__main__":
    main()
