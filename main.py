from bot import create_bot

if __name__ == "__main__":
    bot = create_bot()
    print("🤖 Bot đang chạy...")
    bot.run_polling()
    print("🛑 Bot đã dừng.")
