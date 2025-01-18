import os
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import asyncio

# تنظیم FastAPI
app = FastAPI()

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت توکن و آدرس سایت
TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

# ایجاد نمونه Application
application = ApplicationBuilder().token(TOKEN).build()

# بررسی ادمین بودن
async def is_admin(update: Update, user_id: int) -> bool:
    chat_member = await update.effective_chat.get_member(user_id)
    return chat_member.status in ['administrator', 'creator']

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.type == 'private':
        return

    if any(domain in update.message.text.lower() for domain in ['http', 'www', '.com', '.ir', 't.me']):
        if not await is_admin(update, update.effective_user.id):
            await update.message.delete()
            await update.message.reply_text("⛔️ ارسال لینک ممنوع است!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("""
🤖 سلام! من ربات ضد لینک هستم.

برای استفاده از من:
1️⃣ من را به گروه خود اضافه کنید
2️⃣ من را ادمین کنید

قابلیت‌های من:
• جلوگیری از ارسال لینک
""")

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_bot()
    logger.info("Bot started!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot stopped!")