from fastapi import FastAPI
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

app = FastAPI()
TOKEN = os.getenv("TOKEN")

@app.get("/")
async def root():
    return {"status": "Bot is running"}

async def start(update: Update, context) -> None:
    await update.message.reply_text("سلام! برای شروع بازی دوز، لطفاً یکی از گزینه‌ها را انتخاب کنید: /play")

async def play(update: Update, context) -> None:
    await update.message.reply_text("بازی دوز شروع شد! لطفاً علامت خود را انتخاب کنید: X یا O")

async def handle_message(update: Update, context) -> None:
    await update.message.reply_text("لطفاً دستور معتبر را وارد کنید.")

async def keep_alive():
    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"Bot is alive - {current_time}")
        await asyncio.sleep(480)

async def run_bot():
    bot = Application.builder().token(TOKEN).build()
    
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("play", play))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(keep_alive())
    
    await bot.initialize()
    await bot.start()
    await bot.run_polling(poll_interval=3.0)
    
    await bot.stop()
    await bot.shutdown()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)