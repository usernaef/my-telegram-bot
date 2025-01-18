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
                  welcome_msg TEXT, anti_spam INTEGER, 
                  anti_link INTEGER, max_warn INTEGER, locked INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (user_id INTEGER, group_id TEXT, warnings INTEGER)''')
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
    """هندلر اصلی برای تمام پیام‌های متنی"""
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

    elif query.data == 'anti_spam':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT anti_spam FROM groups WHERE group_id=?", (str(chat_id),))
        current_state = c.fetchone()[0]
        new_state = 1 - current_state
        c.execute("UPDATE groups SET anti_spam=? WHERE group_id=?", 
                 (new_state, str(chat_id)))
        conn.commit()
        conn.close()
        
        status = "فعال" if new_state else "غیرفعال"
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        await update_panel(
            query.message,
            f"ضد اسپم با موفقیت {status} شد!",
            keyboard
        )

    elif query.data == 'anti_link':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT anti_link FROM groups WHERE group_id=?", (str(chat_id),))
        current_state = c.fetchone()[0]
        new_state = 1 - current_state
        c.execute("UPDATE groups SET anti_link=? WHERE group_id=?", 
                 (new_state, str(chat_id)))
        conn.commit()
        conn.close()
        
        status = "فعال" if new_state else "غیرفعال"
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        await update_panel(
            query.message,
            f"ضد لینک با موفقیت {status} شد!",
            keyboard
        )

    elif query.data == 'mute':
        keyboard = [
            [InlineKeyboardButton("❌ لغو", callback_data='cancel')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        context.user_data['waiting_for_mute'] = True
        await update_panel(
            query.message,
            "آیدی عددی کاربر را برای میوت کردن ارسال کنید:",
            keyboard
        )

    elif query.data == 'ban':
        keyboard = [
            [InlineKeyboardButton("❌ لغو", callback_data='cancel')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        context.user_data['waiting_for_ban'] = True
        await update_panel(
            query.message,
            "آیدی عددی کاربر را برای بن کردن ارسال کنید:",
            keyboard
        )

    elif query.data == 'cancel':
        context.user_data.clear()
        await show_panel(query, context)

    elif query.data == 'back_to_panel':
        await show_panel(query, context)

    elif query.data == 'warnings':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, warnings FROM warnings WHERE group_id=?", 
                 (str(chat_id),))
        warnings = c.fetchall()
        conn.close()
        
        if warnings:
            warning_text = "لیست اخطارها:\n"
            for user_id, warn_count in warnings:
                warning_text += f"کاربر {user_id}: {warn_count} اخطار\n"
        else:
            warning_text = "هیچ اخطاری ثبت نشده است."
            
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        await update_panel(query.message, warning_text, keyboard)

    elif query.data == 'users':
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_text = "لیست ادمین‌ها:\n"
            for admin in admins:
                admin_text += f"- {admin.user.full_name}"
                if admin.user.username:
                    admin_text += f" (@{admin.user.username})"
                admin_text += "\n"
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
            ]
            await update_panel(query.message, admin_text, keyboard)
        except TelegramError:
            await query.answer("خطا در دریافت لیست ادمین‌ها")

    elif query.data == 'help':
        help_text = """
راهنمای استفاده از ربات:
1️⃣ ابتدا ربات را در گروه خود ادمین کنید
2️⃣ دستور /panel را در گروه ارسال کنید
3️⃣ از طریق پنل مدیریتی، تنظیمات را انجام دهید

قابلیت‌های ربات:
🔒 قفل گروه
📝 تنظیم پیام خوش‌آمد
⚔️ ضد اسپم
🔗 ضد لینک
⚠️ سیستم اخطار
👥 مدیریت کاربران
        """
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_to_panel')]
        ]
        await update_panel(query.message, help_text, keyboard)

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