import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from flask import Flask, request

# تنظیم Flask
app = Flask(__name__)

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت توکن
TOKEN = os.environ['TOKEN']
PORT = int(os.environ.get('PORT', 8080))

# ذخیره کاربران فعال
active_users = {}

# [تمام توابع قبلی بدون تغییر]
# start, button_callback, forward_content, handle_text و غیره را کپی کنید

@app.route('/')
def index():
    return 'Bot is running!'

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    application.process_update(update)
    return 'ok'

def main():
    """تابع اصلی"""
    try:
        global application
        application = ApplicationBuilder().token(TOKEN).build()

        # اضافه کردن هندلرها
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("menu", show_menu))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # هندلرهای انواع محتوا
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        application.add_handler(MessageHandler(filters.ANIMATION, handle_animation))
        application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.LOCATION, handle_location))

        # تنظیم وبهوک
        webhook_url = f"https://[نام-پروژه-شما].onrender.com/{TOKEN}"
        application.bot.set_webhook(webhook_url)
        
        # اجرای Flask
        app.run(host='0.0.0.0', port=PORT)
        
        print("✅ ربات چت روم با موفقیت شروع به کار کرد!")
        
    except Exception as e:
        print(f"❌ خطا: {e}")

if __name__ == '__main__':
    main()