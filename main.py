import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import random
from concurrent.futures import ThreadPoolExecutor

TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
application = Application.builder().token(TOKEN).build()
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔰 HACK", callback_data='hack')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to nullz hack bot!\nWhat would you like to do?",
        reply_markup=reply_markup
    )

async def simulate_hack(message, user_id, context: ContextTypes.DEFAULT_TYPE):
    if user_id in user_states:
        return
    
    user_states[user_id] = True
    
    try:
        hack_steps = [
            "Initializing hack sequence...",
            "Setting up connection...",
            "Scanning target system...", 
            "Finding vulnerabilities...",
            "Bypassing security...",
            "Injecting payload...",
            "Extracting data...",
            "Cleaning traces...",
            "Completing hack..."
        ]

        for step in hack_steps:
            if not user_states.get(user_id):
                break
            try:
                await message.edit_text(step)
                await asyncio.sleep(0.5)
            except:
                continue

        progress_steps = [0, 25, 50, 75, 100]
        for i in progress_steps:
            if not user_states.get(user_id):
                break
            blocks = "▓" * (i // 5)
            spaces = "░" * (20 - (i // 5))
            try:
                await message.edit_text(f"Progress: {blocks}{spaces} {i}%")
                await asyncio.sleep(0.3)
            except:
                continue

        if user_states.get(user_id):
            await message.edit_text("✅ HACK COMPLETE! 🎯\nTarget system compromised!")

    finally:
        if user_id in user_states:
            del user_states[user_id]

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'hack':
        user_id = update.effective_user.id
        message = await query.message.edit_text("Starting hack...")
        asyncio.create_task(simulate_hack(message, user_id, context))

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
        await application.bot.set_webhook(webhook_url)

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_bot()

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)