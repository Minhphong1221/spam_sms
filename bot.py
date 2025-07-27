import os
import asyncio
import datetime
import concurrent.futures
import logging
from collections import defaultdict
from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from spam_sms import *  # Import các hàm spam từ file spam_sms.py

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.bot").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

# Token từ biến môi trường
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ Thiếu biến môi trường TOKEN. Vui lòng đặt TOKEN vào Railway.")
    exit(1)

# 👑 Danh sách ID admin
ADMIN_IDS = [6594643149]  # Nhập đúng Telegram user ID của bạn

# Trạng thái người dùng & giới hạn spam
user_stop_flags = defaultdict(bool)
daily_usage = defaultdict(lambda: {'date': str(datetime.date.today()), 'count': 0})
DAILY_LIMIT = 1000

def is_group_chat(update):
    return update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]

def check_daily_limit(user_id, times):
    today = str(datetime.date.today())
    user_data = daily_usage[user_id]
    if user_data['date'] != today:
        user_data['date'] = today
        user_data['count'] = 0
    if user_data['count'] + times > DAILY_LIMIT:
        return False
    user_data['count'] += times
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
                if user_stop_flags[user_id]:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⛔ <b>{full_name}</b> đã dừng spam. Dùng /spam để tiếp tục.",
                        parse_mode='HTML'
                    )
                    return
                func = SPAM_FUNCTIONS[index % total]
                await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
                index += 1
                count += 1
                await asyncio.sleep(0.3)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ <b>{full_name}</b> đã spam {count} lần tới số <b>{phone}</b>.",
            parse_mode='HTML'
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Lỗi: <code>{str(e)}</code>",
            parse_mode='HTML'
        )

# 📲 Lệnh /spam
async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ dùng trong nhóm.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("❌ Sai cú pháp.\n👉 /spam <số_điện_thoại> <số_lần>")
        return

    try:
        phone = context.args[0]
        times = int(context.args[1]) if len(context.args) > 1 else 1

        if not check_daily_limit(user_id, times):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ <b>{full_name}</b> đã vượt giới hạn {DAILY_LIMIT} lần/ngày!",
                parse_mode='HTML'
            )
            return

        user_stop_flags[user_id] = False

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚀 <b>{full_name}</b> đang spam số <b>{phone}</b> ({times} lần).",
            parse_mode='HTML'
        )

        asyncio.create_task(spam_runner(context, user_id, full_name, phone, times, chat_id))

    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")

# 🛑 Lệnh /stop
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await update.message.reply_text("🛑 Bạn đã dừng spam. Gõ /spam để tiếp tục.", parse_mode='HTML')

# 📊 Lệnh /check
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage[user_id]
    if user_data['date'] != today:
        user_data['date'] = today
        user_data['count'] = 0
    count = user_data['count']
    remaining = DAILY_LIMIT - count
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📊 <b>{update.effective_user.full_name}</b> đã spam {count} lần hôm nay.\n🔋 Còn lại: {remaining} lần.",
        parse_mode='HTML'
    )

# 🌐 Lệnh /ip
async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Kiểm tra địa chỉ IP của bạn tại:\n👉 https://mphongdev-net.vercel.app/",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

# 🆔 Lệnh /id
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Tên: {user.full_name}\n🆔 ID của bạn: <code>{user.id}</code>",
        parse_mode='HTML'
    )

# 🔁 Lệnh /reset (admin)
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id

    if int(admin_id) not in ADMIN_IDS:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Vui lòng reply tin nhắn của người cần reset.", parse_mode='HTML')
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    daily_usage[target_id] = {
        'date': str(datetime.date.today()),
        'count': 0
    }

    await update.message.reply_text(
        f"✅ Đã reset lượt spam cho <b>{target_user.full_name}</b> ({target_id}).",
        parse_mode='HTML'
    )

# 🚀 Lệnh /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 <b>Bot spam SMS</b>\n"
            "/spam <sdt> <solan> — spam SMS\n"
            "/stop — dừng spam của bạn\n"
            "/check — kiểm tra số lượt hôm nay\n"
            "/reset — (admin) reset lượt người dùng (reply tin nhắn)\n"
            "/ip — kiểm tra địa chỉ IP\n"
            "/id — lấy ID Telegram của bạn\n"
            "📅 Giới hạn: 1000 lần/ngày\n"
            "Bot By VŨ MINH PHONG",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Lỗi khi gửi lệnh /start: {e}")

# ✅ Tạo ứng dụng bot
def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("id", id_command))
    return app
