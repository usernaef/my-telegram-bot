import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = os.getenv("TELEGRAM_TOKEN")

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        ['🕹 شروع بازی آنلاین'],
        ['👥 دوستانه', '🎭 سناریو', '⚡️ چالش'],
        ['💰 سکه', '🌟 امتیازات', '👤 پروفایل'],
        ['📣 مزایده', '🌐 سرور', '📚 راهنما']
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('لطفا یکی از گزینه ها را انتخاب کنید:', reply_markup=reply_markup)

def button_response(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('سلام!')

def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    
    # اضافه کردن هندلر برای تمام دکمه‌ها
    buttons = [
        '🕹 شروع بازی آنلاین',
        '👥 دوستانه', '🎭 سناریو', '⚡️ چالش',
        '💰 سکه', '🌟 امتیازات', '👤 پروفایل',
        '📣 مزایده', '🌐 سرور', '📚 راهنما'
    ]
    
    for button in buttons:
        dispatcher.add_handler(MessageHandler(Filters.regex(f'^{button}$'), button_response))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()