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

async def register_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['waiting_for_group'] = True
    await query.message.reply_text("لطفاً ربات را به گروه خود اضافه کرده و سپس آیدی گروه را ارسال کنید.")

async def handle_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.text
    try:
        chat = await context.bot.get_chat(chat_id)
        if chat.type in ['group', 'supergroup']:
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO groups (group_id, admin_id) VALUES (?, ?)",
                     (chat_id, update.effective_user.id))
            conn.commit()
            conn.close()
            context.user_data.clear()
            await update.message.reply_text("گروه با موفقیت ثبت شد!")
        else:
            await update.message.reply_text("این یک گروه معتبر نیست!")
    except:
        await update.message.reply_text("خطا در ثبت گروه. لطفاً مطمئن شوید آیدی گروه صحیح است.")

async def handle_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = update.message.text
    chat_id = update.message.chat_id
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("UPDATE groups SET welcome_msg=? WHERE group_id=?", 
             (welcome_msg, str(chat_id)))
    conn.commit()
    conn.close()
    
    context.user_data.clear()
    await update.message.reply_text("پیام خوش‌آمد با موفقیت تنظیم شد!")

async def handle_mute_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_user_id = int(update.message.text)
        chat_id = update.message.chat_id
        
        if context.user_data.get('waiting_for_mute'):
            await context.bot.restrict_chat_member(
                chat_id, 
                target_user_id,
                ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text(f"کاربر {target_user_id} میوت شد.")
        
        elif context.user_data.get('waiting_for_ban'):
            await context.bot.ban_chat_member(chat_id, target_user_id)
            await update.message.reply_text(f"کاربر {target_user_id} بن شد.")
        
        context.user_data.clear()
        
    except ValueError:
        await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید.")
    except TelegramError as e:
        await update.message.reply_text(f"خطا: {str(e)}")

async def handle_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT anti_spam FROM groups WHERE group_id=?", (chat_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        if chat_id not in spam_cache:
            spam_cache[chat_id] = {}
        if user_id not in spam_cache[chat_id]:
            spam_cache[chat_id][user_id] = []
            
        now = datetime.now()
        spam_cache[chat_id][user_id].append(now)
        
        # حذف پیام‌های قدیمی‌تر از 5 ثانیه
        spam_cache[chat_id][user_id] = [
            msg_time for msg_time in spam_cache[chat_id][user_id]
            if now - msg_time < timedelta(seconds=5)
        ]
        
        if len(spam_cache[chat_id][user_id]) > 5:
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(
                    update.message.chat_id,
                    user_id,
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.now() + timedelta(minutes=5)
                )
                await update.message.reply_text(
                    f"کاربر {user_id} به دلیل اسپم به مدت 5 دقیقه میوت شد."
                )
            except TelegramError:
                pass

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT anti_link FROM groups WHERE group_id=?", (chat_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        if re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 
                    update.message.text):
            try:
                await update.message.delete()
            except TelegramError:
                pass

async def show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
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
            ],
            [
                InlineKeyboardButton("🔇 میوت کاربر", callback_data='mute'),
                InlineKeyboardButton("⛔️ بن کاربر", callback_data='ban')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if isinstance(update, Update):
            context.user_data['panel_message'] = await update.message.reply_text(
                "پنل مدیریت گروه:", 
                reply_markup=reply_markup
            )
        else:  # CallbackQuery
            await update.edit_message_text(
                "پنل مدیریت گروه:",
                reply_markup=reply_markup
            )

async def update_panel(message, new_text, keyboard=None):
    if keyboard is None:
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
            ],
            [
                InlineKeyboardButton("🔇 میوت کاربر", callback_data='mute'),
                InlineKeyboardButton("⛔️ بن کاربر", callback_data='ban')
            ]
        ]
    await message.edit_text(new_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_id = update.effective_user.id

    # بررسی وضعیت‌های انتظار
    if context.user_data.get('waiting_for_welcome'):
        await handle_welcome_message(update, context)
        return

    if context.user_data.get('waiting_for_mute'):
        await handle_mute_ban(update, context)
        return

    if context.user_data.get('waiting_for_ban'):
        await handle_mute_ban(update, context)
        return

    if context.user_data.get('waiting_for_group'):
        await handle_group_id(update, context)
        return

    # بررسی ضد اسپم و ضد لینک
    await handle_spam(update, context)
    await handle_link(update, context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if query.data == 'register_group':
        await register_group_handler(update, context)
        return

    if query.message.chat.type in ['group', 'supergroup']:
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            if user.status not in ['administrator', 'creator']:
                await query.answer("شما ادمین نیستید!")
                return
        except TelegramError:
            await query.answer("خطا در بررسی دسترسی‌ها")
            return

    # Handle other button callbacks...
    await query.answer()
    
    if query.data == 'lock_group':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT locked FROM groups WHERE group_id=?", (str(chat_id),))
        result = c.fetchone()
        current_state = result[0] if result else 0
        new_state = 1 - current_state
        
        try:
            permissions = ChatPermissions(
                can_send_messages=not new_state,
                can_send_media_messages=not new_state,
                can_send_other_messages=not new_state
            )
            await context.bot.set_chat_permissions(chat_id, permissions)
            
            c.execute("UPDATE groups SET locked=? WHERE group_id=?", 
                     (new_state, str(chat_id)))
            conn.commit()
            
            status = "قفل" if new_state else "باز"
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
            ]
            await update_panel(query.message, f"گروه با موفقیت {status} شد!", keyboard)
            
        except TelegramError as e:
            await query.answer(f"خطا در تغییر وضعیت قفل گروه: {str(e)}")
        
        conn.close()

    elif query.data == 'welcome':
        keyboard = [
            [InlineKeyboardButton("❌ لغو", callback_data='cancel')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        context.user_data['waiting_for_welcome'] = True
        await update_panel(
            query.message,
            "پیام خوش‌آمد جدید را ارسال کنید:",
            keyboard
        )

    # Add other button handlers...

async def setup_bot():
    init_db()
    
    # حذف هندلرهای قبلی
    application.handlers.clear()
    
    # اضافه کردن هندلرها با اولویت صحیح
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", show_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_messages
    ))

    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_bot()
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot shut down successfully!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)