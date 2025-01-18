import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import asyncio
from datetime import datetime, timedelta

# تنظیم FastAPI
app = FastAPI()

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت توکن و آدرس سایت
TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

# تنظیمات گروه‌ها
group_settings = {}

# ایجاد نمونه Application در سطح گلوبال
application = ApplicationBuilder().token(TOKEN).build()

# بررسی ادمین بودن
async def is_admin(update: Update, user_id: int) -> bool:
    chat_member = await update.effective_chat.get_member(user_id)
    return chat_member.status in ['administrator', 'creator']

# پنل مدیریت گروه
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("⛔️ شما ادمین نیستید!")
        return

    chat_id = str(update.effective_chat.id)
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'antilink': False,
            'antispam': False,
            'spam_limit': 5,
            'spam_time': 5
        }

    settings = group_settings[chat_id]
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'🔐' if settings['antilink'] else '🔓'} ضد لینک",
                callback_data='toggle_antilink'
            ),
            InlineKeyboardButton(
                f"{'🔐' if settings['antispam'] else '🔓'} ضد اسپم",
                callback_data='toggle_antispam'
            )
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات اسپم", callback_data='spam_settings')
        ],
        [
            InlineKeyboardButton("❌ بستن", callback_data='close_panel')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = """🛠 پنل مدیریت گروه

وضعیت فعلی:
• ضد لینک: {'فعال' if settings['antilink'] else 'غیرفعال'}
• ضد اسپم: {'فعال' if settings['antispam'] else 'غیرفعال'}
• محدودیت پیام: {settings['spam_limit']} پیام در {settings['spam_time']} ثانیه

راهنمای مدیریت:
• ریپلای + بن: مسدود کردن کاربر
• ریپلای + سکوت: محدود کردن کاربر"""

    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = str(query.message.chat_id)
    
    if not await is_admin(update, query.from_user.id):
        await query.answer("⛔️ شما ادمین نیستید!", show_alert=True)
        return
        
    await query.answer()
    
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'antilink': False,
            'antispam': False,
            'spam_limit': 5,
            'spam_time': 5
        }
    
    settings = group_settings[chat_id]
    
    if query.data == 'toggle_antilink':
        settings['antilink'] = not settings['antilink']
        
    elif query.data == 'toggle_antispam':
        settings['antispam'] = not settings['antispam']
        
    elif query.data == 'spam_settings':
        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data='spam_limit_minus'),
                InlineKeyboardButton(f"{settings['spam_limit']}", callback_data='current'),
                InlineKeyboardButton("➕", callback_data='spam_limit_plus')
            ],
            [
                InlineKeyboardButton("برگشت", callback_data='back_to_panel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("تنظیمات ضد اسپم:\nتعداد پیام مجاز:", reply_markup=reply_markup)
        return
        
    elif query.data == 'spam_limit_minus':
        if settings['spam_limit'] > 2:
            settings['spam_limit'] -= 1
            
    elif query.data == 'spam_limit_plus':
        if settings['spam_limit'] < 20:
            settings['spam_limit'] += 1
            
    elif query.data == 'back_to_panel':
        await admin_panel(update, context)
        return
        
    elif query.data == 'close_panel':
        await query.message.delete()
        return
        
    # بروزرسانی پنل
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'🔐' if settings['antilink'] else '🔓'} ضد لینک",
                callback_data='toggle_antilink'
            ),
            InlineKeyboardButton(
                f"{'🔐' if settings['antispam'] else '🔓'} ضد اسپم",
                callback_data='toggle_antispam'
            )
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات اسپم", callback_data='spam_settings')
        ],
        [
            InlineKeyboardButton("❌ بستن", callback_data='close_panel')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"""🛠 پنل مدیریت گروه

وضعیت فعلی:
• ضد لینک: {'فعال' if settings['antilink'] else 'غیرفعال'}
• ضد اسپم: {'فعال' if settings['antispam'] else 'غیرفعال'}
• محدودیت پیام: {settings['spam_limit']} پیام در {settings['spam_time']} ثانیه

راهنمای مدیریت:
• ریپلای + بن: مسدود کردن کاربر
• ریپلای + سکوت: محدود کردن کاربر"""
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# مدیریت پیام‌ها
user_messages = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
        
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    # بررسی دستورات مدیریتی
    if update.message.reply_to_message and await is_admin(update, user_id):
        if update.message.text.lower() == 'بن':
            target_user = update.message.reply_to_message.from_user
            await context.bot.ban_chat_member(chat_id, target_user.id)
            await update.message.reply_text(f"کاربر {target_user.first_name} از گروه مسدود شد.")
            return
            
        elif update.message.text.lower() == 'سکوت':
            target_user = update.message.reply_to_message.from_user
            await context.bot.restrict_chat_member(
                chat_id,
                target_user.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False
                )
            )
            await update.message.reply_text(f"کاربر {target_user.first_name} محدود شد.")
            return
    
    # بررسی تنظیمات گروه
    if chat_id in group_settings:
        settings = group_settings[chat_id]
        
        # بررسی ضد لینک
        if settings['antilink'] and any(domain in update.message.text.lower() for domain in ['http', 'www', '.com', '.ir', 't.me']):
            if not await is_admin(update, user_id):
                await update.message.delete()
                await update.message.reply_text("⛔️ ارسال لینک ممنوع است!")
                return
                
        # بررسی ضد اسپم
        if settings['antispam']:
            if chat_id not in user_messages:
                user_messages[chat_id] = {}
                
            if user_id not in user_messages[chat_id]:
                user_messages[chat_id][user_id] = []
                
            current_time = datetime.now()
            user_messages[chat_id][user_id].append(current_time)
            
            # حذف پیام‌های قدیمی
            user_messages[chat_id][user_id] = [
                msg_time for msg_time in user_messages[chat_id][user_id]
                if current_time - msg_time < timedelta(seconds=settings['spam_time'])
            ]
            
            if len(user_messages[chat_id][user_id]) > settings['spam_limit']:
                if not await is_admin(update, user_id):
                    await context.bot.restrict_chat_member(
                        chat_id,
                        user_id,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_media_messages=False
                        ),
                        until_date=datetime.now() + timedelta(minutes=5)
                    )
                    await update.message.reply_text(f"کاربر {update.effective_user.first_name} به دلیل اسپم به مدت 5 دقیقه محدود شد.")
                    user_messages[chat_id][user_id] = []
                    return

# تنظیم وبهوک و هندلرها
@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    application.add_handler(CommandHandler("panel", admin_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_bot()
    logger.info("Bot started!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot stopped!")