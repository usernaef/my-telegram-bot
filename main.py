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
        [InlineKeyboardButton("🔰 HACK", callback_data='hack')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to nullz hack bot!\nWhat would you like to do?",
        reply_markup=reply_markup
    )

async def simulate_hack(message, context: ContextTypes.DEFAULT_TYPE):
    # Starting sequence
    loading_sequence = [
        "s", "st", "sta", "star", "start", "starti", "startin", "starting",
        "starting h", "starting ha", "starting hac", "starting hack",
        "starting hack.", "starting hack..", "starting hack..."
    ]
    
    for text in loading_sequence:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Port scanning sequence
    port_scan = ["s", "sc", "sca", "scan", "scann", "scanni", "scannin", "scanning", 
                 "scanning p", "scanning po", "scanning por", "scanning port", "scanning ports", 
                 "scanning ports.", "scanning ports..", "scanning ports..."]
    for text in port_scan:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Vulnerability check sequence
    vuln_check = ["c", "ch", "che", "chec", "check", "checki", "checkin", "checking", 
                  "checking v", "checking vu", "checking vul", "checking vuln", 
                  "checking vulns", "checking vulns.", "checking vulns..", "checking vulns..."]
    for text in vuln_check:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Exploiting sequence
    exploit_seq = ["e", "ex", "exp", "expl", "explo", "exploi", "exploit", "exploiti", 
                   "exploitin", "exploiting", "exploiting.", "exploiting..", "exploiting..."]
    for text in exploit_seq:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Access sequence
    access_seq = ["g", "ga", "gai", "gain", "gaini", "gainin", "gaining", 
                  "gaining a", "gaining ac", "gaining acc", "gaining acce", 
                  "gaining acces", "gaining access", "gaining access.", 
                  "gaining access..", "gaining access..."]
    for text in access_seq:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Data extraction sequence
    extract_seq = ["e", "ex", "ext", "extr", "extra", "extrac", "extract", 
                   "extracti", "extractin", "extracting", "extracting d", 
                   "extracting da", "extracting dat", "extracting data", 
                   "extracting data.", "extracting data..", "extracting data..."]
    for text in extract_seq:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    # Progress bar sequence
    progress_steps = [0, 20, 40, 60, 80, 100]
    for i in progress_steps:
        blocks = "▓" * (i // 5)
        spaces = "░" * (20 - (i // 5))
        try:
            await message.edit_text(f"Completing hack: {blocks}{spaces} {i}%")
            await asyncio.sleep(0.3)
        except:
            continue

    # Final success message
    success_seq = ["h", "ha", "hac", "hack", "hack ", "hack c", "hack co", 
                   "hack com", "hack comp", "hack compl", "hack comple", 
                   "hack complet", "hack complete", "hack complete!", 
                   "hack complete! 🎯"]
    for text in success_seq:
        try:
            await message.edit_text(text)
            await asyncio.sleep(0.1)
        except:
            continue

    await asyncio.sleep(1)
    await message.edit_text("✅ HACK COMPLETE! 🎯\nTarget system fully compromised!")

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