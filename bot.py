import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("TOKEN")  # توکن ربات از متغیر محیطی

async def start(update: Update, context) -> None:
    await update.message.reply_text("سلام! برای شروع بازی دوز، لطفاً یکی از گزینه‌ها را انتخاب کنید: /play")

async def play(update: Update, context) -> None:
    await update.message.reply_text("بازی دوز شروع شد! لطفاً علامت خود را انتخاب کنید: X یا O")

async def handle_message(update: Update, context) -> None:
    await update.message.reply_text("لطفاً دستور معتبر را وارد کنید.")

async def main() -> None:
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    await app.initialize()
    await app.start()
    await app.run_polling()
    
    # Properly close the application
    await app.stop()
    await app.shutdown()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())