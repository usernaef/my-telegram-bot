import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# تنظیم FastAPI
app = FastAPI()

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت توکن
TOKEN = os.environ['TOKEN']
PORT = int(os.environ.get('PORT', 8080))

# ذخیره کاربران فعال
active_users = {}

# [تمام توابع قبلی شما بدون تغییر]
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton("🚪 ورود به چت", callback_data='join'),
            InlineKeyboardButton("👥 کاربران آنلاین", callback_data='users')
        ],
        [
            InlineKeyboardButton("❓ راهنما", callback_data='help'),
            InlineKeyboardButton("🚫 خروج", callback_data='leave')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""سلام {user.first_name}! 👋

به چت روم خوش آمدید!
می‌توانید انواع پیام‌ها را ارسال کنید:
• متن 📝
• عکس 📸
• ویدیو 🎥
• گیف 🎞
• استیکر 🎯
• فایل 📁
• ویس 🎤
• موقعیت مکانی 📍"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# [بقیه توابع قبلی شما]

# مسیرهای FastAPI
@app.get("/")
async def root():
    return {"status": "running"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# تنظیم و راه‌اندازی ربات
async def setup_bot():
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

    # تنظیم webhook
    webhook_url = f"https://[my-telegram-botz].onrender.com/{TOKEN}"
    await application.bot.set_webhook(webhook_url)
    logger.info("Webhook set up successfully!")

@app.on_event("startup")
async def startup_event():
    await setup_bot()
    logger.info("Bot started successfully!")