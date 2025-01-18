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
                  anti_link INTEGER, max_warn INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warnings
                 (user_id INTEGER, group_id TEXT, warnings INTEGER)''')
    conn.commit()
    conn.close()

# کش موقت برای مدیریت اسپم
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
    user_id = update.effective_user.id
    context.user_data['waiting_for_group'] = True
    await update.callback_query.message.reply_text(
        "لطفا آیدی گروه را به صورت @groupname ارسال کنید."
    )

async def handle_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_group'):
        group_id = update.message.text
        if group_id.startswith('@'):
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO groups VALUES (?, ?, ?, 1, 1, 3)",
                     (group_id, update.effective_user.id, "خوش آمدید به گروه!"))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"گروه {group_id} با موفقیت ثبت شد.\n"
                "1. ربات را در گروه اضافه کنید\n"
                "2. ربات را ادمین کنید\n"
                "3. دستور /panel را در گروه ارسال کنید"
            )
            context.user_data['waiting_for_group'] = False

async def handle_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'waiting_for_welcome' in context.user_data and context.user_data['waiting_for_welcome']:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("UPDATE groups SET welcome_msg=? WHERE group_id=?", 
                 (update.message.text, str(update.message.chat_id)))
        conn.commit()
        conn.close()
        context.user_data['waiting_for_welcome'] = False
        await update.message.reply_text("پیام خوش‌آمد با موفقیت تنظیم شد!")

async def handle_mute_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'waiting_for_mute' in context.user_data and context.user_data['waiting_for_mute']:
        try:
            user_id = int(update.message.text)
            await context.bot.restrict_chat_member(
                update.message.chat_id,
                user_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text(f"کاربر {user_id} میوت شد!")
        except:
            await update.message.reply_text("خطا در میوت کردن کاربر!")
        context.user_data['waiting_for_mute'] = False

    elif 'waiting_for_ban' in context.user_data and context.user_data['waiting_for_ban']:
        try:
            user_id = int(update.message.text)
            await context.bot.ban_chat_member(update.message.chat_id, user_id)
            await update.message.reply_text(f"کاربر {user_id} بن شد!")
        except:
            await update.message.reply_text("خطا در بن کردن کاربر!")
        context.user_data['waiting_for_ban'] = False

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
        await update.message.reply_text("پنل مدیریت گروه:", reply_markup=reply_markup)

async def handle_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    user_id = update.effective_user.id
    chat_id = str(update.message.chat_id)
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT anti_spam FROM groups WHERE group_id=?", (chat_id,))
    result = c.fetchone()
    conn.close()

    if not result or not result[0]:
        return
    
    if chat_id not in spam_cache:
        spam_cache[chat_id] = {}
    if chat_id not in user_messages:
        user_messages[chat_id] = {}

    current_time = datetime.now()
    
    if user_id in spam_cache[chat_id]:
        spam_cache[chat_id][user_id] = [t for t in spam_cache[chat_id][user_id]
                                      if current_time - t < timedelta(seconds=5)]
    
    if user_id not in spam_cache[chat_id]:
        spam_cache[chat_id][user_id] = []
    spam_cache[chat_id][user_id].append(current_time)
    
    if len(spam_cache[chat_id][user_id]) > 5:
        await update.message.reply_text(f"کاربر {update.effective_user.mention_html()} به دلیل اسپم اخطار گرفت!")
        await add_warning(update, context, user_id, chat_id)

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT anti_link FROM groups WHERE group_id=?", (str(update.message.chat_id),))
    result = c.fetchone()
    conn.close()

    if result and result[0]:
        text = update.message.text or update.message.caption or ""
        if re.search(r'(https?://\S+)', text) or '@' in text or 't.me/' in text:
            await update.message.delete()
            await add_warning(update, context, update.effective_user.id, str(update.message.chat_id))

async def add_warning(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: str):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute("SELECT warnings FROM warnings WHERE user_id=? AND group_id=?", (user_id, chat_id))
    result = c.fetchone()
    
    if result:
        warnings = result[0] + 1
        c.execute("UPDATE warnings SET warnings=? WHERE user_id=? AND group_id=?",
                 (warnings, user_id, chat_id))
    else:
        warnings = 1
        c.execute("INSERT INTO warnings VALUES (?, ?, ?)", (user_id, chat_id, warnings))
    
    conn.commit()
    conn.close()
    
    if warnings >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.send_message(chat_id, f"کاربر به دلیل دریافت {warnings} اخطار از گروه اخراج شد!")
        except TelegramError as e:
            logger.error(f"خطا در بن کردن کاربر: {e}")

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
        try:
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False
            )
            await context.bot.set_chat_permissions(chat_id, permissions)
            await query.answer("گروه قفل شد!")
        except TelegramError:
            await query.answer("خطا در قفل کردن گروه")
    
    elif query.data == 'welcome':
        context.user_data['waiting_for_welcome'] = True
        await query.message.reply_text("پیام خوش‌آمد جدید را ارسال کنید:")
    
    elif query.data == 'anti_spam':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT anti_spam FROM groups WHERE group_id=?", (str(chat_id),))
        current_state = c.fetchone()[0]
        new_state = 1 - current_state
        c.execute("UPDATE groups SET anti_spam=? WHERE group_id=?", (new_state, str(chat_id)))
        conn.commit()
        conn.close()
        state = "فعال" if new_state == 1 else "غیرفعال"
        await query.answer(f"ضد اسپم {state} شد!")
    
    elif query.data == 'anti_link':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT anti_link FROM groups WHERE group_id=?", (str(chat_id),))
        current_state = c.fetchone()[0]
        new_state = 1 - current_state
        c.execute("UPDATE groups SET anti_link=? WHERE group_id=?", (new_state, str(chat_id)))
        conn.commit()
        conn.close()
        state = "فعال" if new_state == 1 else "غیرفعال"
        await query.answer(f"ضد لینک {state} شد!")

    elif query.data == 'mute':
        context.user_data['waiting_for_mute'] = True
        await query.message.reply_text("آیدی عددی کاربر را برای میوت کردن ارسال کنید:")

    elif query.data == 'ban':
        context.user_data['waiting_for_ban'] = True
        await query.message.reply_text("آیدی عددی کاربر را برای بن کردن ارسال کنید:")

    elif query.data == 'warnings':
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, warnings FROM warnings WHERE group_id=?", (str(chat_id),))
        warnings = c.fetchall()
        conn.close()
        
        if warnings:
            warning_text = "لیست اخطارها:\n"
            for user_id, warn_count in warnings:
                warning_text += f"کاربر {user_id}: {warn_count} اخطار\n"
        else:
            warning_text = "هیچ اخطاری ثبت نشده است."
        await query.message.reply_text(warning_text)

    elif query.data == 'users':
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admin_text = "لیست ادمین‌ها:\n"
            for admin in admins:
                admin_text += f"- {admin.user.full_name} (@{admin.user.username})\n"
            await query.message.reply_text(admin_text)
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
        await query.message.reply_text(help_text)

async def setup_bot():
    init_db()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", show_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # اضافه کردن هندلرهای پیام به ترتیب اولویت
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_id))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_welcome_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mute_ban))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spam))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

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