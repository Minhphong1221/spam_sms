from telegram.ext import Updater, CommandHandler
from telegram import Chat
import concurrent.futures
import threading
from spam_sms import *  # Import các hàm spam ở đây
import datetime

# Danh sách các hàm spam từ file spam_sms
SPAM_FUNCTIONS = [
    v for k, v in globals().items()
    if callable(v) and not k.startswith("__") and k.islower()
]

user_stop_flags = {}
daily_usage = {}  # {user_id: {'date': 'YYYY-MM-DD', 'count': int}}
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
    except TypeError as e:
        print(f"⚠️ TypeError ở {func.__name__}(): {e}")
    except Exception as e:
        print(f"❌ Lỗi khi gọi {func.__name__}(): {e}")

def spam_command(update, context):
    if not is_group_chat(update):
        update.message.reply_text("⚠️ Bot chỉ sử dụng được trong nhóm.")
        return

    user = update.effective_user
    user_id = user.id
    full_name = user.full_name
    chat_id = update.effective_chat.id

    print(f"📥 Nhận lệnh /spam từ user: {user_id} - {full_name}")

    try:
        args = context.args
        phone = args[0]
        times = int(args[1]) if len(args) > 1 else 1

        if not check_daily_limit(user_id, times):
            context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ <b>{full_name}</b> đã vượt quá giới hạn {DAILY_LIMIT} lần spam mỗi ngày!",
                parse_mode='HTML'
            )
            return

        user_stop_flags[user_id] = False

        context.bot.send_message(
            chat_id=chat_id,
            text=f"🚀 <b>{full_name}</b> đã bắt đầu spam số <b>{phone}</b> ({times} lần).",
            parse_mode='HTML'
        )

        def run_spam():
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    for _ in range(times):
                        if user_stop_flags.get(user_id, False):
                            context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⛔ <b>{full_name}</b> đã dừng spam.",
                                parse_mode='HTML'
                            )
                            return

                        for func in SPAM_FUNCTIONS:
                            if callable(func):
                                executor.submit(call_with_log, func, phone)

                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ <b>{full_name}</b> đã spam xong số <b>{phone}</b>.",
                    parse_mode='HTML'
                )
            except Exception as e:
                context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {e}")

        threading.Thread(target=run_spam).start()

    except (IndexError, ValueError):
        update.message.reply_text("❌ Sai cú pháp.\n👉 Dùng: /spam <số_điện_thoại> <số_lần>")

def stop_command(update, context):
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name

    user_stop_flags[user_id] = True

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🛑 <b>{full_name}</b> đã gửi lệnh dừng spam.",
        parse_mode='HTML'
    )

def check_command(update, context):
    if not is_group_chat(update):
        update.message.reply_text("⚠️ Lệnh này chỉ dùng trong nhóm.")
        return

    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    today = str(datetime.date.today())

    user_data = daily_usage.get(user_id, {'date': today, 'count': 0})
    if user_data['date'] != today:
        user_data = {'date': today, 'count': 0}

    count = user_data['count']
    remaining = DAILY_LIMIT - count

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📊 <b>{full_name}</b>, bạn đã spam <b>{count}</b> lần hôm nay.\n"
             f"🔋 Còn lại: <b>{remaining}</b> lần.",
        parse_mode='HTML'
    )

def start_command(update, context):
    update.message.reply_text(
        "🤖 <b>Tôi là bot spam SMS Minh Phong</b>\n\n"
        "📱 <b>Lệnh sử dụng:</b>\n"
        "➔ <code>/spam &lt;sdt&gt; &lt;solan&gt;</code> - bắt đầu spam\n"
        "➔ <code>/stop</code> - dừng spam\n"
        "➔ <code>/check</code> - xem số lần spam đã dùng\n\n"
        "🌐 <b>Thông tin liên hệ:</b>\n"
        "🔸 Zalo: <b>0813539155</b>\n"
        "🔷 Facebook: <a href='https://www.facebook.com/minh.phong.914984?locale=vi_VN'>minh.phong</a>\n\n"
        "💡 <b>Lưu ý:</b> Mỗi người chỉ được spam tối đa 1000 lần/ngày và chỉ sử dụng trong nhóm.\n"
        "⚠️ <b>Chúc bạn spam vui vẻ!</b>\n\n"
        "<i>Bot by VŨ MINH PHONG</i>",
        parse_mode='HTML'
    )

def main():
    updater = Updater("8374042933:AAHbaUMkbxPaqp4EDpxdilfmGbUFqhPFmyA", use_context=True)  # 🔒 Thay bằng token thật
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("spam", spam_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    dp.add_handler(CommandHandler("check", check_command))

    print("🤖 Bot đã khởi động...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
