import os
import nest_asyncio
import asyncio
import concurrent.futures
import datetime
from flask import Flask, request
from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from spam_sms import *  # Import các hàm spam

# ==== CẤU HÌNH BOT ====
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DOMAIN = os.environ.get("DOMAIN", "https://your-app-name.up.railway.app")
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{DOMAIN}{WEBHOOK_PATH}"

# ==== TẠO ỨNG DỤNG ====
flask_app = Flask(__name__)
app = ApplicationBuilder().token(TOKEN).build()

# ==== CẤU HÌNH SPAM ====
SPAM_FUNCTIONS = [v for k, v in globals().items() if callable(v) and not k.startswith("__") and k.islower()]
user_stop_flags = {}
daily_usage = {}
DAILY_LIMIT = 1000

def is_group_chat(update): return update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]

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
        func(phone)
    except Exception as e:
        print(f"Lỗi khi gọi {func.__name__}: {e}")

async def spam_runner(context, user_id, full_name, phone, times, chat_id):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for _ in range(times):
            if user_stop_flags.get(user_id, False):
                await context.bot.send_message(chat_id=chat_id, text=f"{full_name} đã dừng spam.")
                return
            for func in SPAM_FUNCTIONS:
                await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
    await context.bot.send_message(chat_id=chat_id, text=f"✅ {full_name} đã spam xong {phone}.")

# ==== COMMAND HANDLERS ====
async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update): return await update.message.reply_text("⚠️ Chỉ dùng trong nhóm.")
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    chat_id = update.effective_chat.id
    if len(context.args) < 1:
        return await update.message.reply_text("❌ Sai cú pháp: /spam <sdt> <solan>")
    try:
        phone = context.args[0]
        times = int(context.args[1]) if len(context.args) > 1 else 1
        if not check_daily_limit(user_id, times):
            return await context.bot.send_message(chat_id=chat_id, text=f"❌ {full_name} vượt giới hạn {DAILY_LIMIT} lần/ngày.")
        user_stop_flags[user_id] = False
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 {full_name} đang spam {phone} ({times} lần).")
        asyncio.create_task(spam_runner(context, user_id, full_name, phone, times, chat_id))
    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🛑 {update.effective_user.full_name} đã dừng spam.")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update): return await update.message.reply_text("⚠️ Dùng trong nhóm.")
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    count = user_data['count']
    remaining = DAILY_LIMIT - count
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📊 {update.effective_user.full_name} đã spam {count} lần hôm nay.\n🔋 Còn lại: {remaining} lần.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot spam SMS\n/spam <sdt> <solan>\n/stop\n/check")

# ==== ĐĂNG KÝ COMMAND ====
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("spam", spam_command))
app.add_handler(CommandHandler("stop", stop_command))
app.add_handler(CommandHandler("check", check_command))

# ==== FLASK ROUTES ====
@flask_app.route("/")
def index():
    return "🤖 Bot đang chạy..."

@flask_app.route("/set_webhook")
def set_webhook():
    asyncio.get_event_loop().run_until_complete(app.bot.set_webhook(WEBHOOK_URL))
    return f"✅ Webhook đã thiết lập: {WEBHOOK_URL}"

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    asyncio.get_event_loop().create_task(app.process_update(update))
    return "OK"

# ==== KHỞI CHẠY ====
if __name__ == "__main__":
    nest_asyncio.apply()
    port = int(os.environ.get("PORT", 8080))
    asyncio.get_event_loop().run_until_complete(app.initialize())
    flask_app.run(host="0.0.0.0", port=port)
