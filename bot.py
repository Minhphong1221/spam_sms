import os
import asyncio
import datetime
import concurrent.futures
import logging
from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from spam_sms1 import *  # <-- Import tất cả API từ spam_sms1.py

# --- Bật logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Lấy TOKEN từ biến môi trường ---
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ Thiếu biến môi trường TOKEN. Vui lòng đặt TOKEN vào biến môi trường Railway.")
    exit(1)

# --- Biến trạng thái ---
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
        print(f"❌ Lỗi khi gọi {func.__name__}(): {e}")

async def spam_runner(context, user_id, full_name, phone, times, chat_id):
    SPAM_FUNCTIONS = [
        v for k, v in globals().items()
        if callable(v) and not k.startswith("__") and k.islower()
    ]

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            total = len(SPAM_FUNCTIONS)
            index = 0
            count = 0

            while count < times:
                if user_stop_flags.get(user_id, False):
                    try:
                        await context.bot.send_message(chat_id=chat_id,
                            text=f"⛔ <b>{full_name}</b> đã dừng spam. Dùng /spam để tiếp tục.",
                            parse_mode='HTML')
                    except Exception as e:
                        logger.error(f"Lỗi khi gửi tin nhắn dừng spam: {e}")
                    return

                func = SPAM_FUNCTIONS[index % total]
                await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
                index += 1
                count += 1

        try:
            await context.bot.send_message(chat_id=chat_id,
                text=f"✅ <b>{full_name}</b> đã spam {count} tới số <b>{phone}</b>.",
                parse_mode='HTML')
        except Exception as e:
            logger.error(f"Lỗi khi gửi tin nhắn hoàn thành: {e}")

    except Exception as e:
        try:
            await context.bot.send_message(chat_id=chat_id,
                text=f"❌ Lỗi: <code>{str(e)}</code>",
                parse_mode='HTML')
        except Exception as e2:
            logger.error(f"Lỗi khi gửi lỗi nội bộ: {e2}")

async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ dùng trong nhóm.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("❌ Sai cú pháp.👉 /spam <số_điện_thoại> <số_lần>")
        return

    try:
        phone = context.args[0]
        times = int(context.args[1]) if len(context.args) > 1 else 1

        if not check_daily_limit(user_id, times):
            try:
                await context.bot.send_message(chat_id=chat_id,
                    text=f"❌ <b>{full_name}</b> đã vượt giới hạn {DAILY_LIMIT} lần/ngày!",
                    parse_mode='HTML')
            except Exception as e:
                logger.error(f"Lỗi khi gửi thông báo giới hạn: {e}")
            return

        user_stop_flags[user_id] = False
        try:
            await context.bot.send_message(chat_id=chat_id,
                text=f"🚀 <b>{full_name}</b> đang spam số <b>{phone}</b> ({times} lần).",
                parse_mode='HTML')
        except Exception as e:
            logger.error(f"Lỗi khi gửi thông báo bắt đầu: {e}")

        asyncio.create_task(spam_runner(context, user_id, full_name, phone, times, chat_id))

    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    try:
        await update.message.reply_text("🛑 Bạn đã dừng spam. Gõ /spam để tiếp tục.", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Lỗi khi gửi tin nhắn dừng: {e}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}
    count = user_data['count']
    remaining = DAILY_LIMIT - count

    try:
        await context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"📊 <b>{update.effective_user.full_name}</b> đã spam {count} lần hôm nay.
🔋 Còn lại: {remaining} lần.",
            parse_mode='HTML')
    except Exception as e:
        logger.error(f"Lỗi khi gửi thống kê: {e}")

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🌐 Kiểm tra địa chỉ IP của bạn tại:
👉 https://mphongdev-net.vercel.app/",
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Lỗi khi gửi link IP: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 <b>Bot spam SMS</b>
"
            "/spam <số_điện_thoại> <số_lần> — spam SMS
"
            "/stop — dừng spam của bạn
"
            "/check — kiểm tra số lượt hôm nay
"
            "/ip — kiểm tra địa chỉ IP
"
            "📅 Giới hạn: 1000 lần/ngày
"
            "Bot By VŨ MINH PHONG",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Lỗi khi gửi lệnh /start: {e}")

def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("ip", ip_command))
    return app
