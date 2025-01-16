import os
from telegram.ext import Application, CommandHandler
from telegram import Update

async def start(update, context):
    await update.message.reply_text("سلام! من فعال هستم!")

def main():
    try:
        token = os.getenv("TOKEN")
        if not token:
            print("Error: TOKEN environment variable is not set")
            return
            
        print(f"Starting bot...")
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        print("Added handlers...")
        app.run_polling()
        print("Bot is running...")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()