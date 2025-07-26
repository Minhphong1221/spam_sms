from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import concurrent.futures
import asyncio
import datetime
from spam_sms import *  # <-- file spam_sms.py chứa các hàm spam

TOKEN = "8374042933:AAFq8KFtX5UypTOv04wIJsJ40pz2oEA0bj0"

bot_stopped = False  # Cờ kiểm soát bot đang dừng
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
    global bot_stopped
    SPAM_FUNCTIONS = [
        v for k, v in globals().items()
        if callable(v) and not k.startswith("__") and k.islower()
    ]

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _ in range(times):
                if user_stop_flags.get(user_id, False) or bot_stopped:
                    await context.bot.send_message(chat_id=chat_id, text=f"⛔ <b>{full_name}</b> đã dừng spam.", parse_mode='HTML')
                    return
                for func in SPAM_FUNCTIONS:
                    await asyncio.get_event_loop().run_in_executor(executor, call_with_log, func, phone)

        await context.bot.send_message(chat_id=chat_id, text=f"✅ <b>{full_name}</b> đã spam xong số <b>{phone}</b>.", parse_mode='HTML')

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {e}")


async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_stopped

    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Bot chỉ dùng trong nhóm.")
        return

    if bot_stopped:
        bot_stopped = False
        await update.message.reply_text("✅ Bot đã khởi động lại.")
        return

    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    if len(context.args) < 1:
        await update.message.reply_text("❌ Sai cú pháp.\n👉 /spam <số_điện_thoại> <số_lần>")
        return

    try:
        phone = context.args[0]
        times = int(context.args[1]) if len(context.args) > 1 else 1

        if not check_daily_limit(user_id, times):
            await context.bot.send_message(chat_id=chat_id, text=f"❌ <b>{full_name}</b> đã vượt giới hạn {DAILY_LIMIT} lần/ngày!", parse_mode='HTML')
            return

        user_stop_flags[user_id] = False
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 <b>{full_name}</b> đang spam số <b>{phone}</b> ({times} lần).", parse_mode='HTML')
        asyncio.create_task(spam_runner(context, user_id, full_name, phone, times, chat_id))

    except ValueError:
        await update.message.reply_text("❌ Số lần phải là số nguyên.")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_stopped
    bot_stopped = True
    await update.message.reply_text("🛑 Bot đã dừng hoàn toàn.\n✅ Gõ /spam để chạy lại.", parse_mode='HTML')
    print("⚠️ Bot logic đã bị dừng bằng /stop")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group_chat(update):
        await update.message.reply_text("⚠️ Lệnh này chỉ dùng trong nhóm.")
        return

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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
   await update.message.reply_text(
    "🤖 <b>Bot spam SMS</b>\n"
    "/spam &lt;sdt&gt; &lt;lần&gt; — spam SMS\n"
    "/stop — dừng bot hoàn toàn\n"
    "/check — kiểm tra số lượt hôm nay\n"
    "Bot By VŨ MINH PHONG\n",
    parse_mode='HTML'
)

# ==== RUN BOT ====
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("check", check_command))

    print("🤖 Bot đang chạy...")
    app.run_polling()
