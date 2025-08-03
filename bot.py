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

# Mỗi người dùng có riêng flag dừng
user_stop_flags = defaultdict(bool)
ngl_stop_flags = defaultdict(bool)
daily_usage = defaultdict(lambda: {'date': str(datetime.date.today()), 'count': 0})

# NGL handler state
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
        func(phone)
    except Exception as e:
        print(f"❌ Lỗi {func.__name__}: {e}")

# === Import các hàm spam SMS ===
from spam_sms import *

# === Spam SMS ===
async def spam_runner(context, user_id, full_name, phone, times, chat_id):
    SPAM_FUNCTIONS = [
        v for k, v in globals().items()
        if callable(v) and not k.startswith("__") and k.islower()
    ]
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            index = 0
            count = 0
            while count < times:
                if user_stop_flags[user_id]:
                    await context.bot.send_message(chat_id=chat_id, text="⛔️ Bạn đã dừng spam.")
                    return
                func = SPAM_FUNCTIONS[index % len(SPAM_FUNCTIONS)]
                await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)
                index += 1
                count += 1
                await asyncio.sleep(0.3)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ <b>{full_name}</b> đã spam {count} lần đến số <b>{phone}</b>.",
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
        await update.message.reply_text("❌ Dùng: /spam &lt;số điện thoại&gt; &lt;số lần&gt;", parse_mode='HTML')
        return

    phone = args[0]
    if not phone.isdigit():
        await update.message.reply_text("❌ Số điện thoại không hợp lệ.")
        return

    try:
        times = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Số lần spam phải là số.")
        return

    if not check_daily_limit(user_id, times):
        await update.message.reply_text("❌ Vượt quá giới hạn 1000 lần/ngày.")
        return

    user_stop_flags[user_id] = False
    await update.message.reply_text("🚀 Bắt đầu spam...")
    await spam_runner(context, user_id, full_name, phone, times, chat_id)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_stop_flags[user_id] = True
    await update.message.reply_text("🛑 Bạn đã dừng spam.")

# === NGL ===
async def send_ngl_questions(chat_id, context, username, question, count):
    user_id = chat_id
    for i in range(count):
        if ngl_stop_flags[user_id]:
            await context.bot.send_message(chat_id=chat_id, text="⛔️ Bạn đã dừng gửi NGL.")
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
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi lần {i + 1}: {e}")
        await asyncio.sleep(random.uniform(0.5, 1.5))
    await context.bot.send_message(chat_id=chat_id, text=f"✅ Đã gửi {count} câu hỏi.")

async def ngl_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧑 Nhập username NGL:")
    return ASK_NGL_USER

async def ngl_input_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ngl_user_data[chat_id] = {'username': update.message.text.strip()}
    await update.message.reply_text("🔢 Nhập số lượng câu hỏi:")
    return ASK_NGL_COUNT

async def ngl_input_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Vui lòng nhập số.")
        return ASK_NGL_COUNT
    ngl_user_data[chat_id]['count'] = int(text)
    await update.message.reply_text("💬 Nhập nội dung câu hỏi:")
    return ASK_NGL_QUESTION

async def ngl_input_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = ngl_user_data.pop(chat_id)
    data['question'] = update.message.text.strip()
    ngl_stop_flags[chat_id] = False
    await update.message.reply_text("🚀 Đang gửi...")
    await send_ngl_questions(chat_id, context, data['username'], data['question'], data['count'])
    return ConversationHandler.END

async def ngl_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy thao tác.")
    return ConversationHandler.END

async def stop_ngl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ngl_stop_flags[update.effective_chat.id] = True
    await update.message.reply_text("🛑 Bạn đã dừng gửi NGL.")

# === Các lệnh khác ===
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    user_data = daily_usage[user_id]
    if user_data['date'] != today:
        user_data['date'] = today
        user_data['count'] = 0
    await update.message.reply_text(
        f"📊 Đã spam {user_data['count']} lần.\n🔋 Còn {DAILY_LIMIT - user_data['count']} lần.",
        parse_mode='HTML'
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot spam SMS + NGL\n"
        "/spam &lt;sdt&gt; &lt;số lần&gt; — spam SMS\n"
        "/ngl — gửi câu hỏi NGL\n"
        "/stop — dừng spam\n"
        "/stopngl — dừng NGL\n"
        "/check — kiểm tra lượt\n"
        "/cancel — hủy nhập\n"
        "\nBot By VŨ MINH PHONG",
        parse_mode='HTML'
    )


# === Khởi tạo bot ===
def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("stopngl", stop_ngl_command))
    app.add_handler(CommandHandler("check", check_command))

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

    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "Bắt đầu"),
            BotCommand("spam", "Spam SMS"),
            BotCommand("ngl", "Gửi NGL"),
            BotCommand("stop", "Dừng spam"),
            BotCommand("stopngl", "Dừng NGL"),
            BotCommand("check", "Kiểm tra lượt"),
            BotCommand("cancel", "Hủy nhập")
        ])
        await application.bot.delete_webhook(drop_pending_updates=True)

    app.post_init = post_init
    return app