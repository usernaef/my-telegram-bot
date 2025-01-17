import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    keyboard = [
        [KeyboardButton("🕹 شروع بازی آنلاین")],
        [
            KeyboardButton("👥 دوستانه"),
            KeyboardButton("🎭 سناریو"),
            KeyboardButton("⚡️ چالش")
        ],
        [
            KeyboardButton("💰 سکه"),
            KeyboardButton("🌟 امتیازات"), 
            KeyboardButton("👤 پروفایل")
        ],
        [
            KeyboardButton("📣 مزایده"),
            KeyboardButton("🌐 سرور"),
            KeyboardButton("📚 راهنما")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = f"سلام {update.effective_user.first_name}! به ربات خوش آمدید."
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های دریافتی"""
    if update.message.text:
        await update.message.reply_text("سلام!")

@app.get("/")
async def root():
    return {"status": "running"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    """دریافت و پردازش به‌روزرسانی‌های تلگرام"""
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    """تنظیم اولیه ربات"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        try:
            await application.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
    else:
        logger.warning("RENDER_URL not set, webhook not configured")

@app.on_event("startup")
async def startup_event():
    """رویداد راه‌اندازی برنامه"""
    await application.initialize()
    await setup_bot()
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    """رویداد خاموش شدن برنامه"""
    await application.shutdown()
    logger.info("Bot shut down successfully!")