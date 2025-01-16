import os
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
import telegram

TOKEN = os.environ.get('TOKEN')
bot = telegram.Bot(token=TOKEN)

def start(update, context):
    update.message.reply_text('سلام! فایل خود را ارسال کنید تا آپلود شود.')

def handle_file(update, context):
    file = update.message.document
    if file:
        try:
            # دریافت اطلاعات فایل
            file_name = file.file_name
            file_id = file.file_id
            
            # دانلود فایل
            new_file = context.bot.get_file(file_id)
            
            # اطلاع‌رسانی به کاربر
            update.message.reply_text(f"فایل {file_name} با موفقیت دریافت شد!")
            
            # می‌توانید اینجا مسیر ذخیره‌سازی فایل را مشخص کنید
            # new_file.download(f'downloads/{file_name}')
            
            # ارسال لینک دانلود به کاربر
            file_url = new_file.file_path
            update.message.reply_text(f"لینک دانلود فایل شما:\n{file_url}")
            
        except Exception as e:
            update.message.reply_text(f"خطا در آپلود فایل: {str(e)}")
    else:
        update.message.reply_text("لطفاً یک فایل ارسال کنید.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # تعریف هندلرها
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_file))

    # شروع بات
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()