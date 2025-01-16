import os
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
import telegram
from flask import Flask

# اضافه کردن Flask برای وب سرور
app = Flask(__name__)

TOKEN = os.environ.get('TOKEN')
PORT = int(os.environ.get('PORT', 8080))

bot = telegram.Bot(token=TOKEN)

def start(update, context):
    update.message.reply_text('سلام! فایل خود را ارسال کنید تا آپلود شود.')

def handle_file(update, context):
    file = update.message.document
    if file:
        try:
            file_name = file.file_name
            file_id = file.file_id
            new_file = context.bot.get_file(file_id)
            update.message.reply_text(f"فایل {file_name} با موفقیت دریافت شد!")
            file_url = new_file.file_path
            update.message.reply_text(f"لینک دانلود فایل شما:\n{file_url}")
        except Exception as e:
            update.message.reply_text(f"خطا در آپلود فایل: {str(e)}")
    else:
        update.message.reply_text("لطفاً یک فایل ارسال کنید.")

# اضافه کردن مسیر اصلی برای وب سرور
@app.route('/')
def home():
    return 'Bot is running!'

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_file))

    # تنظیم وبهوک به جای polling
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://[نام-پروژه-شما].onrender.com/{TOKEN}"
    )
    
    # اجرای Flask
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()