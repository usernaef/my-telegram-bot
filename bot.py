import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# تنظیم FastAPI
app = FastAPI()

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت توکن و آدرس سایت
TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

# ذخیره کاربران فعال
active_users = {}

# ایجاد نمونه Application در سطح گلوبال
application = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton("🚪 ورود به چت", callback_data='join'),
            InlineKeyboardButton("👥 کاربران آنلاین", callback_data='users')
        ],
        [
            InlineKeyboardButton("❓ راهنما", callback_data='help'),
            InlineKeyboardButton("🚫 خروج", callback_data='leave')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""سلام {user.first_name}! 👋

به چت روم خوش آمدید!
می‌توانید انواع پیام‌ها را ارسال کنید:
• متن 📝
• عکس 📸
• ویدیو 🎥
• گیف 🎞
• استیکر 🎯
• فایل 📁
• ویس 🎤
• موقعیت مکانی 📍"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌ها"""
    query = update.callback_query
    user = query.from_user
    
    await query.answer()
    
    if query.data == 'join':
        if user.id not in active_users:
            active_users[user.id] = {
                'name': user.first_name,
                'chat_id': query.message.chat_id
            }
            await query.message.reply_text("✅ شما با موفقیت وارد چت روم شدید!")
            for uid, uinfo in active_users.items():
                if uid != user.id:
                    try:
                        await context.bot.send_message(
                            chat_id=uinfo['chat_id'],
                            text=f"🟢 {user.first_name} وارد چت روم شد!"
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام: {e}")
        else:
            await query.message.reply_text("شما قبلاً در چت روم حضور دارید!")
            
    elif query.data == 'leave':
        if user.id in active_users:
            user_name = active_users[user.id]['name']
            del active_users[user.id]
            await query.message.reply_text("✅ شما از چت روم خارج شدید!")
            for uid, uinfo in active_users.items():
                try:
                    await context.bot.send_message(
                        chat_id=uinfo['chat_id'],
                        text=f"🔴 {user_name} از چت روم خارج شد!"
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام: {e}")
        else:
            await query.message.reply_text("شما در چت روم حضور ندارید!")
            
    elif query.data == 'users':
        if not active_users:
            await query.message.reply_text("❌ هیچ کاربری در چت روم حضور ندارد!")
        else:
            users_text = "👥 کاربران آنلاین:\n\n"
            for _, user_info in active_users.items():
                users_text += f"• {user_info['name']}\n"
            await query.message.reply_text(users_text)
            
    elif query.data == 'help':
        help_text = """🤖 راهنمای چت روم:

• برای چت کردن باید اول وارد چت روم شوید
• می‌توانید هر نوع محتوایی ارسال کنید
• پیام‌های شما به همه اعضای آنلاین ارسال می‌شود

دستورات:
/start - شروع مجدد و نمایش منو
/menu - نمایش منوی اصلی"""
        await query.message.reply_text(help_text)

async def forward_content(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str):
    """ارسال محتوا به همه کاربران"""
    user = update.effective_user
    user_id = user.id
    
    if user_id not in active_users:
        keyboard = [[InlineKeyboardButton("🚪 ورود به چت", callback_data='join')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ برای ارسال محتوا، اول باید وارد چت روم شوید!",
            reply_markup=reply_markup
        )
        return
    
    sender_name = active_users[user_id]['name']
    
    for uid, uinfo in active_users.items():
        if uid != user_id:
            try:
                if content_type == 'text':
                    await context.bot.send_message(
                        chat_id=uinfo['chat_id'],
                        text=f"💬 {sender_name}:\n{update.message.text}"
                    )
                elif content_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=uinfo['chat_id'],
                        photo=update.message.photo[-1].file_id,
                        caption=f"📸 {sender_name}:" + (f"\n{update.message.caption}" if update.message.caption else "")
                    )
                elif content_type == 'video':
                    await context.bot.send_video(
                        chat_id=uinfo['chat_id'],
                        video=update.message.video.file_id,
                        caption=f"🎥 {sender_name}:" + (f"\n{update.message.caption}" if update.message.caption else "")
                    )
                elif content_type == 'animation':
                    await context.bot.send_animation(
                        chat_id=uinfo['chat_id'],
                        animation=update.message.animation.file_id,
                        caption=f"🎞 {sender_name}:" + (f"\n{update.message.caption}" if update.message.caption else "")
                    )
                elif content_type == 'sticker':
                    await context.bot.send_sticker(
                        chat_id=uinfo['chat_id'],
                        sticker=update.message.sticker.file_id
                    )
                elif content_type == 'voice':
                    await context.bot.send_voice(
                        chat_id=uinfo['chat_id'],
                        voice=update.message.voice.file_id,
                        caption=f"🎤 {sender_name}"
                    )
                elif content_type == 'document':
                    await context.bot.send_document(
                        chat_id=uinfo['chat_id'],
                        document=update.message.document.file_id,
                        caption=f"📁 {sender_name}:" + (f"\n{update.message.caption}" if update.message.caption else "")
                    )
                elif content_type == 'location':
                    await context.bot.send_location(
                        chat_id=uinfo['chat_id'],
                        latitude=update.message.location.latitude,
                        longitude=update.message.location.longitude
                    )
            except Exception as e:
                logger.error(f"خطا در ارسال محتوا: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'text')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'photo')

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'video')

async def handle_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'animation')

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'sticker')

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'voice')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'document')

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_content(update, context, 'location')

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی اصلی"""
    keyboard = [
        [
            InlineKeyboardButton("🚪 ورود به چت", callback_data='join'),
            InlineKeyboardButton("👥 کاربران آنلاین", callback_data='users')
        ],
        [
            InlineKeyboardButton("❓ راهنما", callback_data='help'),
            InlineKeyboardButton("🚫 خروج", callback_data='leave')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("منوی اصلی:", reply_markup=reply_markup)

@app.get("/")
async def root():
    return {"status": "running"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    """دریافت و پردازش به‌روزرسانی‌های تلگرام"""
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    """تنظیم اولیه ربات"""
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", show_menu))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # هندلرهای انواع محتوا
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.ANIMATION, handle_animation))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        try:
            await application.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
    else:
        logger.warning("RENDER_URL not set, webhook not configured")

@app.on_event("startup")
async def startup_event():
    """رویداد راه‌اندازی برنامه"""
    await application.initialize()
    await setup_bot()
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    """رویداد خاموش شدن برنامه"""
    await application.shutdown()
    logger.info("Bot shut down successfully!")