import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import TelegramError
import sqlite3
from datetime import datetime, timedelta
import re
from typing import Dict, Set

# تنظیمات اولیه
TOKEN = os.getenv('TOKEN')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دیتابیس
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (group_id TEXT PRIMARY KEY, admin_id INTEGER, 
                  welcome_msg TEXT, anti_spam INTEGER DEFAULT 0, 
                  anti_link INTEGER DEFAULT 0, max_warn INTEGER DEFAULT 3, 
                  locked INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (user_id INTEGER, group_id TEXT, warnings INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# کش موقت
spam_cache: Dict[str, Dict[int, list]] = {}
user_messages: Dict[str, Dict[int, int]] = {}
warned_users: Dict[str, Set[int]] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ ثبت گروه", callback_data='register_group')],
        [InlineKeyboardButton("📚 راهنما", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "سلام! به ربات مدیریت گروه خوش آمدید.\n"
        "برای شروع، گروه خود را ثبت کنید و ربات را ادمین کنید.",
        reply_markup=reply_markup
    )

async def show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔒 قفل گروه", callback_data='lock_group'),
            InlineKeyboardButton("📝 پیام خوش‌آمد", callback_data='welcome')
        ],
        [
            InlineKeyboardButton("⚔️ ضد اسپم", callback_data='anti_spam'),
            InlineKeyboardButton("🔗 ضد لینک", callback_data='anti_link')
        ],
        [
            InlineKeyboardButton("⚠️ اخطارها", callback_data='warnings'),
            InlineKeyboardButton("👥 مدیریت کاربران", callback_data='users')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("پنل مدیریت گروه:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'register_group':
        context.user_data['registering'] = True
        await query.message.reply_text("لطفاً ربات را به گروه اضافه کرده و ادمین کنید.")
        
    elif query.data == 'lock_group':
        chat_id = str(query.message.chat_id)
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT locked FROM groups WHERE group_id=?", (chat_id,))
        current_state = c.fetchone()[0]
        new_state = 1 - current_state
        
        try:
            permissions = ChatPermissions(
                can_send_messages=not new_state,
                can_send_media_messages=not new_state,
                can_send_other_messages=not new_state
            )
            await context.bot.set_chat_permissions(query.message.chat_id, permissions)
            c.execute("UPDATE groups SET locked=? WHERE group_id=?", (new_state, chat_id))
            conn.commit()
            status = "قفل" if new_state else "باز"
            await query.message.reply_text(f"گروه با موفقیت {status} شد!")
        except TelegramError as e:
            await query.message.reply_text(f"خطا: {str(e)}")
        finally:
            conn.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
        
    chat_id = str(update.message.chat_id)
    user_id = update.effective_user.id
    
    # بررسی اسپم
    if chat_id not in spam_cache:
        spam_cache[chat_id] = {}
    if user_id not in spam_cache[chat_id]:
        spam_cache[chat_id][user_id] = []
        
    now = datetime.now()
    spam_cache[chat_id][user_id].append(now)
    spam_cache[chat_id][user_id] = [t for t in spam_cache[chat_id][user_id] 
                                   if now - t < timedelta(seconds=5)]
    
    if len(spam_cache[chat_id][user_id]) > 5:
        try:
            await update.message.delete()
            await context.bot.restrict_chat_member(
                update.message.chat_id,
                user_id,
                ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=5)
            )
            await update.message.reply_text(f"کاربر {user_id} به دلیل اسپم محدود شد.")
        except TelegramError:
            pass

def main():
    # ساخت نمونه اپلیکیشن
    application = Application.builder().token(TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", show_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # راه‌اندازی دیتابیس
    init_db()
    
    # شروع پولینگ
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()