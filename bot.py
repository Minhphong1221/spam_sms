import os
import asyncio
import datetime
import concurrent.futures
from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from spam_sms import *  # <-- Import tất cả API từ spam_sms.py

# --- Lấy TOKEN từ biến môi trường ---
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ Thiếu biến môi trường TOKEN. Vui lòng đặt TOKEN vào biến môi trường Railway.")
    exit(1)

# --- Biến trạng thái ---
user_stop_flags = {}
user_spam_tasks = {}  # Để lưu tiến trình spam của từng user
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
        print(f"❌ Lỗi khi gọi {func.__name__}(): {e}")

async def spam_runner(context, user_id, full_name, phone, times, chat_id):
    SPAM_FUNCTIONS = [
        v for k, v in globals().items()
        if callable(v) and not k.startswith("__") and k.islower()
    ]

    if user_id in user_spam_tasks and user_spam_tasks[user_id]['remaining'] > 0:
        current_index = user_spam_tasks[user_id]['current_index']
        remaining = user_spam_tasks[user_id]['remaining']
    else:
        current_index = 0
        remaining = times
        user_spam_tasks[user_id] = {
            'phone': phone,
            'remaining': times,
            'current_index': 0
        }

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            while remaining > 0:
                if user_stop_flags.get(user_id, False):
                    await context.bot.send_message(chat_id=chat_id,
                        text=f"⛔ <b>{full_name}</b> đã dừng spam. Dùng /spam để tiếp tục.",
                        parse_mode='HTML')
                    return
                for i in range(current_index, len(SPAM_FUNCTIONS)):
                    func = SPAM_FUNCTIONS[i]
                    await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
                    user_spam_tasks[user_id]['current_index'] = i + 1
                    if user_stop_flags.get(user_id, False):
                        return
                current_index = 0
                user_spam_tasks[user_id]['current_index'] = 0
                remaining -= 1
                user_spam_tasks[user_id]['remaining'] = remaining

        await context.bot.send_message(chat_id=chat_id,
            text=f"✅ <b>{full_name}</b> đã spam xong số <b>{phone}</b>.",
            parse_mode='HTML')
        del user_spam_tasks[user_id]

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {e}")

async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ dùng trong nhóm.")
        return

    if len(context.args) < 1 and user_id not in user_spam_tasks:
        await update.message.reply_text("❌ Sai cú pháp.\n👉 /spam <số_điện_thoại> <số_lần>")
        return

    try:
        if user_id in user_spam_tasks:
            phone = user_spam_tasks[user_id]['phone']
            remaining = user_spam_tasks[user_id]['remaining']
        else:
            phone = context.args[0]
            remaining = int(context.args[1]) if len(context.args) > 1 else 1

        if not check_daily_limit(user_id, remaining):
            await context.bot.send_message(chat_id=chat_id,
                text=f"❌ <b>{full_name}</b> đã vượt giới hạn {DAILY_LIMIT} lần/ngày!",
                parse_mode='HTML')
            return

        user_stop_flags[user_id] = False
        await context.bot.send_message(chat_id=chat_id,
            text=f"🚀 <b>{full_name}</b> đang spam số <b>{phone}</b> ({remaining} lần).",
            parse_mode='HTML')

        asyncio.create_task(spam_runner(context, user_id, full_name, phone, remaining, chat_id))

    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await update.message.reply_text("🛑 Bạn đã dừng spam. Gõ /spam để tiếp tục.", parse_mode='HTML')

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}
    count = user_data['count']
    remaining = DAILY_LIMIT - count

    await context.bot.send_message(chat_id=update.effective_chat.id,
        text=f"📊 <b>{update.effective_user.full_name}</b> đã spam {count} lần hôm nay.\n🔋 Còn lại: {remaining} lần.",
        parse_mode='HTML')

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Kiểm tra địa chỉ IP của bạn tại:\n👉 https://mphongdev-net.vercel.app/",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Bot spam SMS</b>\n"
        "/spam <sdt> <lần> — spam SMS hoặc tiếp tục\n"
        "/stop — dừng spam của bạn\n"
        "/check — kiểm tra số lượt hôm nay\n"
        "/ip — kiểm tra địa chỉ IP\n"
        "📅 Giới hạn: 1000 lần/ngày\n"
        "Bot By VŨ MINH PHONG",
        parse_mode='HTML'
    )

def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("ip", ip_command))

    return app
