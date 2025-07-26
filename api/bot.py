from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request
import asyncio
import nest_asyncio
import os
import datetime
import concurrent.futures

from spam_sms import *  # Các hàm spam SMS bạn tự định nghĩa

TOKEN = "8374042933:AAEDyyxEUxHR8ebGSUJRjrn7XEctT_zhYL0"
DOMAIN = "https://empowering-appreciation-production-9e9b.up.railway.app"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{DOMAIN}{WEBHOOK_PATH}"

# --- Global ---
user_stop_flags = {}
daily_usage = {}
DAILY_LIMIT = 1000

# --- Flask + Telegram App ---
flask_app = Flask(__name__)
bot_app = ApplicationBuilder().token(TOKEN).build()

# --- Check nhóm ---
def is_group_chat(update):
    return update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]

# --- Giới hạn spam ---
def check_daily_limit(user_id, times):
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}
    if user_data['count'] + times > DAILY_LIMIT:
        return False
    user_data['count'] += times
    daily_usage[user_id] = user_data
    return True

def call_with_log(func, phone):
    try:
        print(f"📨 Gọi {func.__name__}({phone})")
        func(phone)
    except Exception as e:
        print(f"❌ Lỗi: {func.__name__}: {e}")

SPAM_FUNCTIONS = [
    v for k, v in globals().items()
    if callable(v) and not k.startswith("__") and k.islower()
]

# --- Lệnh bot ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot spam SMS.\n/spam <sdt> <solan>\n/stop\n/check", parse_mode='HTML')

async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ hoạt động trong nhóm.")
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    phone = context.args[0] if len(context.args) > 0 else None
    times = int(context.args[1]) if len(context.args) > 1 else 1

    if not phone or not phone.isdigit():
        await update.message.reply_text("❌ Sử dụng: /spam <sdt> <solan>")
        return

    if not check_daily_limit(user.id, times):
        await update.message.reply_text("❌ Vượt giới hạn 1000 lần/ngày.")
        return

    user_stop_flags[user.id] = False
    await update.message.reply_text(f"🚀 Đang spam số {phone} ({times} lần)")

    async def runner():
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _ in range(times):
                if user_stop_flags.get(user.id, False):
                    await context.bot.send_message(chat_id, text="⛔ Đã dừng spam.")
                    return
                for func in SPAM_FUNCTIONS:
                    await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
        await context.bot.send_message(chat_id, text=f"✅ Đã spam xong số {phone}.")

    asyncio.create_task(runner())

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_stop_flags[update.effective_user.id] = True
    await update.message.reply_text("🛑 Đã dừng spam.")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}
    count = user_data['count']
    await update.message.reply_text(f"📊 Hôm nay bạn đã spam {count}/{DAILY_LIMIT} lần.")

# --- Đăng ký handler ---
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("spam", spam_command))
bot_app.add_handler(CommandHandler("stop", stop_command))
bot_app.add_handler(CommandHandler("check", check_command))

# --- Route test ---
@flask_app.route("/")
def index():
    return "✅ Bot đang chạy."

# --- Đặt webhook ---
@flask_app.route("/set_webhook")
async def set_webhook():
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    return f"✅ Webhook đã được thiết lập: {WEBHOOK_URL}"

# --- Nhận update từ Telegram ---
@flask_app.post(WEBHOOK_PATH)
async def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return "OK"

# --- Chạy ---
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(bot_app.initialize())
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)
