import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import random

TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔰 START HACK", callback_data='hack')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to nullz hack bot\nWhat would you like to do?",
        reply_markup=reply_markup
    )

async def simulate_typing(message, final_text):
    current_text = ""
    for char in final_text:
        current_text += char
        await message.edit_text(current_text)
        await asyncio.sleep(0.1)

async def simulate_hack(message, context: ContextTypes.DEFAULT_TYPE):
    loading_sequence = [
        "s", "st", "sta", "star", "start", "starti", "startin", "starting",
        "starting h", "starting ha", "starting hac", "starting hack",
        "starting hack.", "starting hack..", "starting hack..."
    ]
    
    for text in loading_sequence:
        await message.edit_text(text)
        await asyncio.sleep(0.1)

    hack_steps = [
        "🔍 SCANNING TARGET SYSTEM...\n```\nInitiating reconnaissance...\nGathering system info...\n```",
        "⚡️ PORT SCANNING...\n```\nPORT   STATE   SERVICE\n22     OPEN    SSH\n80     OPEN    HTTP\n443    OPEN    HTTPS\n```",
        "🔐 CHECKING VULNERABILITIES...\n```\nDetected: SQL Injection\nDetected: XSS\nDetected: RCE\n```",
        "💻 EXPLOITING SYSTEM...\n```\nexploit = '\\x90\\x90\\x90\\x90'\nshellcode loaded...\nBypass security...\n```",
        "📡 GAINING ACCESS...\n```\nAccess granted!\nsudo privileges acquired\nConnecting to mainframe...\n```",
        "📥 DOWNLOADING DATA...\n```\nDownloading: ███████████ 100%\nData extraction complete!\n```",
        "✅ HACK COMPLETE!\n```\n$ whoami\nroot\n$ system compromised\n```"
    ]
    
    for step in hack_steps:
        await message.edit_text(step, parse_mode='Markdown')
        await asyncio.sleep(1)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'hack':
        message = await query.message.edit_text("Initializing hack sequence...")
        await simulate_hack(message, context)

@app.get("/")
async def root():
    return {"status": "running"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
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
    await application.initialize()
    await setup_bot()
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot shut down successfully!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)