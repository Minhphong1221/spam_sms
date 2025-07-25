from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import concurrent.futures
import asyncio
import datetime
from spam_sms import *  # <-- file này bạn phải có
from flask import Flask, request
import os
import nest_asyncio

# === Cấu hình bot & webhook ===
TOKEN = "8374042933:AAEDyyxEUxHR8ebGSUJRjrn7XEctT_zhYL0"
DOMAIN = "https://empowering-appreciation-production-9e9b.up.railway.app"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{DOMAIN}{WEBHOOK_PATH}"

# === Flask App ===
flask_app = Flask(__name__)

# === Bot Telegram ===
app = ApplicationBuilder().token(TOKEN).build()

# === Các hàm spam từ spam_sms.py (đảm bảo bạn đã định nghĩa đúng) ===
SPAM_FUNCTIONS = [
    v for k, v in globals().items()
    if callable(v) and not k.startswith("__") and k.islower()
]

user_stop_flags = {}
daily_usage = {}
DAILY_LIMIT = 1000

def is_group_chat(update):
    return update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]

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
        print(f"❌ Lỗi {func.__name__}: {e}")

async def spam_runner(context, user_id, full_name, phone, times, chat_id):
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _ in range(times):
                if user_stop_flags.get(user_id, False):
                    await context.bot.send_message(chat_id=chat_id, text=f"⛔ <b>{full_name}</b> đã dừng spam.", parse_mode='HTML')
                    return
                for func in SPAM_FUNCTIONS:
                    await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)

        await context.bot.send_message(chat_id=chat_id, text=f"✅ <b>{full_name}</b> đã spam xong số <b>{phone}</b>.", parse_mode='HTML')

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {e}")

# === Các lệnh bot
async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ dùng trong nhóm.")
        return

    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    if len(context.args) < 1:
        await update.message.reply_text("❌ Sai cú pháp.\n👉 /spam <sdt> <solan>")
        return

    try:
        phone = context.args[0]
        times = int(context.args[1]) if len(context.args) > 1 else 1

        if not check_daily_limit(user_id, times):
            await context.bot.send_message(chat_id=chat_id, text=f"❌ <b>{full_name}</b> vượt giới hạn {DAILY_LIMIT} lần/ngày!", parse_mode='HTML')
            return

        user_stop_flags[user_id] = False
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 <b>{full_name}</b> đang spam <b>{phone}</b> ({times} lần).", parse_mode='HTML')
        asyncio.create_task(spam_runner(context, user_id, full_name, phone, times, chat_id))

    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🛑 {update.effective_user.full_name} đã dừng spam.", parse_mode='HTML')

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Dùng trong nhóm.")
        return
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}
    count = user_data['count']
    remaining = DAILY_LIMIT - count
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📊 {update.effective_user.full_name} đã spam {count} lần hôm nay.\n🔋 Còn lại: {remaining} lần.", parse_mode='HTML')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Bot spam SMS</b>\n"
        "/spam <sdt> <solan> - spam\n"
        "/stop - dừng\n"
        "/check - kiểm tra\n",
        parse_mode='HTML'
    )

# === Đăng ký lệnh bot
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("spam", spam_command))
app.add_handler(CommandHandler("stop", stop_command))
app.add_handler(CommandHandler("check", check_command))

# === Route test
@flask_app.route("/")
def home():
    return "🤖 Bot đang chạy..."

# === Route nhận webhook từ Telegram
@flask_app.post(WEBHOOK_PATH)
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    await app.process_update(update)
    return "OK"

# === Route để gọi set webhook bằng trình duyệt (tùy chọn)
@flask_app.route("/set_webhook")
async def manual_set_webhook():
    await app.bot.set_webhook(WEBHOOK_URL)
    return f"Webhook đã thiết lập: {WEBHOOK_URL}"

# === Chạy app
async def main():
    await app.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook đã set: {WEBHOOK_URL}")
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
