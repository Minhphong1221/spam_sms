import os
import asyncio
import datetime
import concurrent.futures
import logging
import random
import urllib.parse
from collections import defaultdict

import httpx
from telegram import Update, Chat, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)

# === Config ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ Thiếu biến môi trường TOKEN.")
    exit(1)

ADMIN_IDS = [1087968824]
DAILY_LIMIT = 1000
user_stop_flags = defaultdict(bool)
ngl_stop_flags = defaultdict(bool)
daily_usage = defaultdict(lambda: {'date': str(datetime.date.today()), 'count': 0})

# === NGL handler state ===
ASK_NGL_USER, ASK_NGL_COUNT, ASK_NGL_QUESTION = range(3)
ngl_user_data = {}

# === Utility ===
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

# === Spam SMS (từ spam_sms.py) ===
from spam_sms import *

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
                        text=f"⛔ <b>{full_name}</b> đã dừng spam.",
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

async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("❌ Dùng: /spam <số điện thoại> <số lần>")
        return

    phone = args[0].strip()
    if not phone.isdigit() or len(phone) < 8:
        await update.message.reply_text("❌ Số điện thoại không hợp lệ.")
        return

    try:
        times = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Số lần spam phải là số.")
        return

    if not check_daily_limit(user_id, times):
        await update.message.reply_text(f"❌ Vượt quá giới hạn {DAILY_LIMIT} lần/ngày.")
        return

    user_stop_flags[user_id] = False
    await update.message.reply_text("🚀 Bắt đầu spam...")
    await spam_runner(context, user_id, full_name, phone, times, chat_id)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await update.message.reply_text("🛑 Bạn đã dừng spam.", parse_mode='HTML')

# === Gửi câu hỏi ngl.link ===
async def send_ngl_questions(chat_id, context, username, question, sl):
    user_id = chat_id
    for i in range(sl):
        if ngl_stop_flags[user_id]:
            await context.bot.send_message(chat_id=chat_id, text="⛔ Bạn đã dừng gửi câu hỏi NGL.")
            return

        deviceId = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=32))
        headers = {
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://ngl.link',
            'referer': f'https://ngl.link/{username}',
            'x-requested-with': 'XMLHttpRequest'
        }
        data = f"username={urllib.parse.quote(username)}&question={urllib.parse.quote(question)}&deviceId={deviceId}&gameSlug=&referrer="

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post("https://ngl.link/api/submit", data=data, headers=headers, timeout=10)
                res.raise_for_status()
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi gửi lần {i + 1}: {e}")

        await asyncio.sleep(random.uniform(0.5, 2.0))

    ngl_stop_flags[user_id] = False  # Reset cờ hiệu sau khi hoàn tất
    await context.bot.send_message(chat_id=chat_id, text=f"🎉 Đã hoàn tất gửi {sl} câu hỏi.")


# === NGL các bước ===
async def ngl_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧑 Nhập username NGL phía sau link (ví dụ:minhphong140906):")
    return ASK_NGL_USER

async def ngl_input_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ngl_user_data[chat_id] = {'username': update.message.text.strip()}
    await update.message.reply_text("🔢 Nhập số lượng câu hỏi muốn gửi:")
    return ASK_NGL_COUNT

async def ngl_input_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Vui lòng nhập số.")
        return ASK_NGL_COUNT
    ngl_user_data[chat_id]['sl'] = int(text)
    await update.message.reply_text("💬 Nhập nội dung câu hỏi muốn gửi:")
    return ASK_NGL_QUESTION

async def ngl_input_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ngl_user_data[chat_id]['question'] = update.message.text.strip()
    data = ngl_user_data.pop(chat_id)
    user_id = update.effective_user.id
    ngl_stop_flags[user_id] = False
    await update.message.reply_text("🚀 Đang gửi câu hỏi...")
    await send_ngl_questions(chat_id, context, data['username'], data['question'], data['sl'])
    return ConversationHandler.END

async def ngl_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy thao tác gửi NGL.")
    return ConversationHandler.END

async def stop_ngl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ngl_stop_flags[user_id] = True
    await update.message.reply_text("🛑 Bạn đã dừng gửi câu hỏi NGL.", parse_mode='HTML')

# === Các lệnh khác giữ nguyên ===

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
        text=f"📊 <b>{update.effective_user.full_name}</b> đã spam {count} lần.\n🔋 Còn lại: {remaining} lần.",
        parse_mode='HTML'
    )

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Kiểm tra địa chỉ IP:\n👉 https://mphongdev-net.vercel.app/",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Tên: {user.full_name}\n🆔 ID của bạn: <code>{user.id}</code>",
        parse_mode='HTML'
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if int(admin_id) not in ADMIN_IDS:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Reply người cần reset.", parse_mode='HTML')
        return

    target_user = update.message.reply_to_message.from_user
    daily_usage[target_user.id] = {'date': str(datetime.date.today()), 'count': 0}

    await update.message.reply_text(
        f"✅ Đã reset lượt spam cho <b>{target_user.full_name}</b>.",
        parse_mode='HTML'
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 <b>Bot spam SMS + NGL</b>\n"
            "/spam &lt;sdt&gt; &lt;số_lần&gt; — spam SMS\n"
            "/ngl — gửi câu hỏi ẩn danh ngl.link\n"
            "/stop — dừng spam\n"
            "/stopngl — dừng gửi ngl\n"
            "/check — xem lượt spam hôm nay\n"
            "/reset — reset lượt spam (admin)\n"
            "/ip — kiểm tra IP\n"
            "/id — lấy ID Telegram\n"
            "/cancel — hủy thao tác đang nhập\n"
            "📅 Giới hạn: 1000 lần/ngày\n"
            "Bot by VŨ MINH PHONG",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Lỗi khi gửi lệnh /start: {e}")

# === Khởi tạo bot ===
def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    # === Thêm handler ===
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("stopngl", stop_ngl_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("id", id_command))

    # === Conversation handler cho NGL ===
    ngl_conv = ConversationHandler(
        entry_points=[CommandHandler("ngl", ngl_start)],
        states={
            ASK_NGL_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ngl_input_user)],
            ASK_NGL_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ngl_input_count)],
            ASK_NGL_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ngl_input_question)],
        },
        fallbacks=[CommandHandler("cancel", ngl_cancel)],
    )
    app.add_handler(ngl_conv)

    # === Hàm set command và gỡ webhook ===
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "Bắt đầu bot"),
            BotCommand("spam", "Spam số điện thoại"),
            BotCommand("ngl", "Gửi câu hỏi ẩn danh NGL"),
            BotCommand("stop", "Dừng spam"),
            BotCommand("stopngl", "Dừng gửi NGL"),
            BotCommand("check", "Kiểm tra số lượt hôm nay"),
            BotCommand("ip", "Kiểm tra địa chỉ IP"),
            BotCommand("id", "Lấy ID Telegram"),
            BotCommand("reset", "Reset lượt spam (admin)"),
            BotCommand("cancel", "Hủy nhập khi gửi NGL"),
        ])
        await application.bot.delete_webhook(drop_pending_updates=True)  # Gỡ webhook để dùng polling

    app.post_init = post_init
    return app
