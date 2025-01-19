import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("TOKEN")

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
        await asyncio.sleep(480)  # هر 8 دقیقه

async def main() -> None:
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Create keep_alive task
    asyncio.create_task(keep_alive())
    
    # Start the bot
    await app.initialize()
    await app.start()
    await app.run_polling(poll_interval=3.0)
    
    # Properly close the application
    await app.stop()
    await app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())