import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import TelegramError
from fastapi import FastAPI, Request
import os
from typing import Dict, Set
import sqlite3
import re

# تنظیمات اولیه
TOKEN = os.getenv('TOKEN')
PORT = int(os.getenv('PORT', '8080'))
RENDER_URL = os.getenv('RENDER_URL')

app = FastAPI()
application = Application.builder().token(TOKEN).build()
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
                 (user_id INTEGER, group_id TEXT, warnings INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, group_id))''')
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

async def register_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.message.chat.type == 'private':
        await query.message.reply_text("لطفا این دستور را در چت خصوصی اجرا کنید.")
        return
        
    context.user_data['waiting_for_group'] = True
    await query.message.reply_text("لطفاً ربات را به گروه خود اضافه کرده و سپس دستور /panel را در گروه ارسال کنید.")

async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except TelegramError:
        return False

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
        
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    # بررسی ضد اسپم
    await handle_spam(update, context)
    
    # بررسی ضد لینک 
    await handle_link(update, context)
    
    # بررسی پیام خوش‌آمد برای اعضای جدید
    if update.message.new_chat_members:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT welcome_msg FROM groups WHERE group_id=?", (chat_id,))
        result = c.fetchone()
        conn.close()
        
        if result and result[0]:
            for member in update.message.new_chat_members:
                welcome_text = result[0].replace("{user}", member.first_name)
                await update.message.reply_text(welcome_text)

async def show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند به پنل دسترسی داشته باشند.")
        return
        
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

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await check_admin(update, context):
        await query.message.reply_text("فقط ادمین‌ها می‌توانند از این دکمه‌ها استفاده کنند.")
        return
        
    chat_id = str(query.message.chat.id)
    
    if query.data == 'lock_group':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT locked FROM groups WHERE group_id=?", (chat_id,))
        result = c.fetchone()
        current_state = result[0] if result else 0
        new_state = 1 - current_state
        
        try:
            permissions = ChatPermissions(
                can_send_messages=not new_state,
                can_send_media_messages=not new_state,
                can_send_other_messages=not new_state
            )
            await context.bot.set_chat_permissions(query.message.chat_id, permissions)
            
            c.execute("UPDATE groups SET locked=? WHERE group_id=?", 
                     (new_state, chat_id))
            conn.commit()
            
            status = "قفل" if new_state else "باز"
            await query.message.reply_text(f"گروه با موفقیت {status} شد!")
            
        except TelegramError as e:
            await query.message.reply_text(f"خطا در تغییر وضعیت قفل گروه: {str(e)}")
        
        conn.close()

async def setup_webhook():
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup_event():
    init_db()
    await application.initialize()
    await setup_webhook()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", show_panel))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        handle_group_message
    ))
    
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot shutdown successfully!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)