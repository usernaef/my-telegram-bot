from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from datetime import datetime, timedelta
import logging
import re
import json

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# تنظیمات پایه
TOKEN = "YOUR_BOT_TOKEN"
ADMIN_IDS = [] # شناسه عددی ادمین‌ها
GROUP_SETTINGS = {} # تنظیمات هر گروه

class GroupSettings:
    def __init__(self):
        self.anti_link = False
        self.anti_spam = False
        self.spam_limit = 5
        self.spam_time = 60 # ثانیه
        self.user_messages = {} # برای کنترل اسپم

async def is_admin(update: Update, user_id: int) -> bool:
    """بررسی ادمین بودن کاربر"""
    chat_member = await update.effective_chat.get_member(user_id)
    return chat_member.status in ['administrator', 'creator']

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل مدیریت"""
    if not await is_admin(update, update.effective_user.id):
        return
    
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SETTINGS:
        GROUP_SETTINGS[chat_id] = GroupSettings()
    
    settings = GROUP_SETTINGS[chat_id]
    
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if settings.anti_link else '❌'} ضد لینک", 
                               callback_data='toggle_antilink'),
            InlineKeyboardButton(f"{'✅' if settings.anti_spam else '❌'} ضد اسپم", 
                               callback_data='toggle_antispam')
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات اسپم", callback_data='spam_settings')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 پنل مدیریت گروه:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش دکمه‌های پنل"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    
    if not await is_admin(update, query.from_user.id):
        await query.answer("شما ادمین نیستید!")
        return
        
    settings = GROUP_SETTINGS.get(chat_id, GroupSettings())
    
    if query.data == 'toggle_antilink':
        settings.anti_link = not settings.anti_link
        await query.edit_message_text(
            text=f"ضد لینک: {'فعال' if settings.anti_link else 'غیرفعال'}",
            reply_markup=query.message.reply_markup
        )
    
    elif query.data == 'toggle_antispam':
        settings.anti_spam = not settings.anti_spam
        await query.edit_message_text(
            text=f"ضد اسپم: {'فعال' if settings.anti_spam else 'غیرفعال'}",
            reply_markup=query.message.reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های گروه"""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    settings = GROUP_SETTINGS.get(chat_id, GroupSettings())
    
    # بررسی دستور بن
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
                permissions=ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text(f"کاربر {target_user.first_name} در حالت سکوت قرار گرفت.")
            return
    
    # بررسی لینک
    if settings.anti_link:
        if re.search(r'(https?://\S+)', update.message.text or ''):
            if not await is_admin(update, user_id):
                await update.message.delete()
                await update.message.reply_text("ارسال لینک در این گروه ممنوع است!")
                return
    
    # بررسی اسپم
    if settings.anti_spam:
        current_time = datetime.now()
        if user_id not in settings.user_messages:
            settings.user_messages[user_id] = []
        
        settings.user_messages[user_id].append(current_time)
        
        # حذف پیام‌های قدیمی‌تر از محدوده زمانی
        settings.user_messages[user_id] = [
            msg_time for msg_time in settings.user_messages[user_id]
            if current_time - msg_time < timedelta(seconds=settings.spam_time)
        ]
        
        if len(settings.user_messages[user_id]) > settings.spam_limit:
            if not await is_admin(update, user_id):
                await context.bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.now() + timedelta(minutes=5)
                )
                await update.message.reply_text(
                    f"کاربر به دلیل اسپم به مدت 5 دقیقه در حالت سکوت قرار گرفت."
                )

async def setup_bot():
    """راه‌اندازی ربات"""
    application = Application.builder().token(TOKEN).build()
    
    # تعریف هندلرها
    application.add_handler(CommandHandler("panel", show_admin_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # شروع ربات
    await application.initialize()
    await application.start()
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(setup_bot())