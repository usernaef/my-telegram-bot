import os
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import asyncio

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

target_group_id = None

async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception:
        return False

async def check_links_periodically():
    while True:
        await asyncio.sleep(600)  # هر 10 دقیقه
        try:
            if target_group_id:
                try:
                    async for message in application.bot.get_chat_history(target_group_id, limit=100):
                        if message.text and any(domain in message.text.lower() 
                            for domain in ['http', 'www', '.com', '.ir', 't.me']):
                            if not await is_admin(target_group_id, message.from_user.id):
                                try:
                                    await message.delete()
                                except Exception as e:
                                    logger.error(f"Error deleting message: {e}")
                except Exception as e:
                    logger.error(f"Error checking group: {e}")
        except Exception as e:
            logger.error(f"Error in periodic check: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    
    global target_group_id
    if target_group_id is None and update.effective_chat.type != 'private':
        target_group_id = chat_id

    if update.effective_chat.type == 'private':
        return

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("""
🤖 سلام! من ربات ضد لینک هستم.

برای استفاده از من:
1️⃣ من را به گروه خود اضافه کنید
2️⃣ من را ادمین کنید

قابلیت‌های من:
• حذف خودکار لینک‌ها هر 10 دقیقه
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
    
    asyncio.create_task(check_links_periodically())
    
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