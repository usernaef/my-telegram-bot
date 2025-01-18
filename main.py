import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import random

# تنظیمات اولیه
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RENDER_URL = os.getenv("RENDER_URL")

# تنظیم لاگر
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ایجاد نمونه‌های برنامه
app = FastAPI()
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    keyboard = [
        [InlineKeyboardButton("🔰 HACK", callback_data='hack')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "سلام به ربات nullz hack خوش آمدید\nچه کاری میخواهید انجام دهید؟",
        reply_markup=reply_markup
    )

async def simulate_hack(message, context: ContextTypes.DEFAULT_TYPE):
    """شبیه‌سازی فرآیند هک"""
    hack_steps = [
        "⚡️ شروع عملیات هک...",
        "🔍 اسکن پورت‌های باز...\n```\nPORT     STATE    SERVICE\n21/tcp   open     ftp\n22/tcp   open     ssh\n80/tcp   open     http\n```",
        "🔑 تلاش برای یافتن آسیب‌پذیری‌ها...\n```\nVulnerability scan in progress...\nCVE-2023-1234 detected\nCVE-2023-5678 detected\n```",
        "💉 تزریق پی‌لود...\n```\npayload = '\\x41\\x42\\x43\\x44\\x45'\ninjecting payload...\n```",
        "📡 دریافت دسترسی...\n```\nAccess granted!\nPrivilege escalation successful\n```",
        "✅ عملیات با موفقیت انجام شد!\n```\nroot@target:~# whoami\nroot\n```"
    ]
    
    current_message = await message.edit_text(hack_steps[0], parse_mode='Markdown')
    
    for step in hack_steps[1:]:
        await asyncio.sleep(2)  # تاخیر 2 ثانیه‌ای بین هر مرحله
        current_message = await current_message.edit_text(step, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کلیک دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'hack':
        message = await query.message.edit_text("🔄 در حال آماده‌سازی عملیات هک...")
        await simulate_hack(message, context)

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