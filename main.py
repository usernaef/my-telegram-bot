import os
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات فعال است. 🤖")

async def main():
    token = os.environ.get("TOKEN")
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())