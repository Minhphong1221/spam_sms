from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BOT_TOKEN = '8374042933:AAGmPBOfr_EOxtwVJMdFqziQLAwTZy1I4-Q'

# Trạng thái trong luồng hội thoại
PHONE, COUNT = range(2)

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Xin chào! Nhập số điện thoại bạn muốn spam:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("✅ Nhập số lần spam:")
    return COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data["count"] = int(update.message.text.strip())
    await update.message.reply_text(f"🚀 Bắt đầu spam {user_data['count']} lần vào số {user_data['phone']}...")

    # Gọi API theo số lần nhập
    for i in range(user_data["count"]):
        try:
            # Thay link API thực tế tại đây (ví dụ mockbin hoặc API spam bạn đang test)
            response = requests.get("https://e8dff6c0815f456f991e9fd08f626b99.api.mockbin.io/", verify=False)
            print(f"[{i+1}] Đã gửi: {response.status_code}")
        except Exception as e:
            print(f"[{i+1}] Lỗi: {e}")

    await update.message.reply_text("✅ Đã hoàn tất spam!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    print("Bot đang chạy...")
    app.run_polling()
