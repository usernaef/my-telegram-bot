import os
import requests
import tempfile
from telegram import Bot, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters  # تغییر در اینجا

# تنظیم توکن ربات از متغیر محیطی
TOKEN = os.getenv('TOKEN')

# تابع برای دانلود ویدیو از URL
def download_video(url):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    tmp_file.write(chunk)
            return tmp_file.name
    return None

# تابع برای ارسال ویدیو به کاربر
def send_video(update, context):
    chat_id = update.message.chat_id
    url = update.message.text

    # دانلود ویدیو
    video_path = download_video(url)
    if video_path:
        try:
            # ارسال ویدیو به کاربر
            with open(video_path, 'rb') as video_file:
                context.bot.send_video(chat_id=chat_id, video=InputFile(video_file))
        finally:
            # حذف فایل از سرور
            os.remove(video_path)
    else:
        update.message.reply_text("مشکلی در دانلود ویدیو پیش آمد.")

# تابع شروع
def start(update, context):
    update.message.reply_text("سلام! لینک ویدیو را برای من بفرستید تا آن را دانلود و برای شما ارسال کنم.")

# تنظیم ربات
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # دستور شروع
    dp.add_handler(CommandHandler("start", start))

    # دریافت لینک ویدیو
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, send_video))

    # شروع ربات
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()