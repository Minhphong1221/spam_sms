
from telegram.ext import Updater, CommandHandler
import concurrent.futures
from spam_sms import *

# Tự động lấy tất cả hàm bắt đầu bằng chữ thường (spam API)
SPAM_FUNCTIONS = [v for k, v in globals().items() if callable(v) and not k.startswith("__") and k.islower()]

def spam_command(update, context):
    print("📥 Nhận lệnh spam")
    try:
        args = context.args
        phone = args[0]
        times = int(args[1]) if len(args) > 1 else 1

        update.message.reply_text(f"🔄 Đang spam {times} lần tới số: {phone}...")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _ in range(times):
                for func in SPAM_FUNCTIONS:
                    executor.submit(call_with_log, func, phone)

        update.message.reply_text("✅ Đã gửi xong yêu cầu spam.")

    except (IndexError, ValueError):
        update.message.reply_text("❌ Sai cú pháp. Dùng: /spam <sdt> <solan>")

def call_with_log(func, phone):
    try:
        print(f"📨 Gọi {func.__name__}({phone})")
        func(phone)
    except Exception as e:
        print(f"❌ Lỗi khi gọi {func.__name__}: {e}")

def main():
    updater = Updater("8374042933:AAHbaUMkbxPaqp4EDpxdilfmGbUFqhPFmyA", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("spam", spam_command))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
