import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = os.getenv("TOKEN")  # توکن ربات از متغیر محیطی

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("سلام! برای شروع بازی دوز، لطفاً یکی از گزینه‌ها را انتخاب کنید: /play")

def play(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("بازی دوز شروع شد! لطفاً علامت خود را انتخاب کنید: X یا O")

def handle_message(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("لطفاً دستور معتبر را وارد کنید.")

def main() -> None:
    updater = Updater(TOKEN)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("play", play))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()