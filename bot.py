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
# ... (phần import và cấu hình giữ nguyên)

# 👑 Danh sách ID admin
ADMIN_IDS = [6594643149]  # Thay đúng ID admin vào đây (đảm bảo kiểu `int`)

# Lệnh mới: /id để xem ID của người dùng
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Tên: {user.full_name}\n🆔 ID của bạn: <code>{user.id}</code>",
        parse_mode='HTML'
    )

# (giữ nguyên các hàm spam_runner, spam_command, stop_command...)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id

    if int(admin_id) not in ADMIN_IDS:  # ⚠️ Đảm bảo so sánh đúng kiểu int
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

# ✅ Cập nhật tạo bot
def create_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("spam", spam_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("id", id_command))  # 💡 Thêm /id
    return app
