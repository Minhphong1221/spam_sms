from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Vô hiệu hóa cảnh báo SSL (chỉ nên dùng khi chắc chắn URL an toàn)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # ⚠️ Thay bằng token bot thật

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! Gõ /run để chạy đoạn mã.")

async def run_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        code_url = "https://e8dff6c0815f456f991e9fd08f626b99.api.mockbin.io/"
        response = requests.get(code_url, verify=False)

        # ⚠️ Cực kỳ nguy hiểm nếu không kiểm soát nội dung từ URL này
        exec(response.text)

        await update.message.reply_text("Đã chạy xong đoạn mã.")
    except Exception as e:
        await update.message.reply_text(f"Lỗi khi chạy mã: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run_code))
    print("Bot đang chạy...")
    app.run_polling()
