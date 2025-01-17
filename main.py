import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler, 
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import random
import asyncio

app = FastAPI()
TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

global_game = None
player_messages = {}

class Player:
    def __init__(self, user):
        self.user = user
        self.role = None
        self.is_alive = True
        self.has_voted = False
        self.has_used_ability = False
        self.votes = 0
        self.self_save_used = False
        self.wrong_shots = 0
        self.can_chat = True
        self.to_be_killed = False
        self.current_selection = None
        self.last_target = None

class GameRoom:
    def __init__(self):
        self.players = []
        self.is_started = False
        self.roles = ["پدرخوانده🚬", "دکتر💉", "کارآگاه🕵‍♂", "اسنایپر🔫", "ردگیر👣"]
        self.player_roles = {}
        self.day_count = 0
        self.is_day = True
        self.chat_enabled = True
        self.night_actions = {}
        self.voting_in_progress = False
        self.votes = {}
        self.doctor_save = None
        self.mafia_kill = None
        self.defense_mode = False
        self.defender = None
        self.defense_votes = {}
        self.final_voting = False
        self.chat_lock = False
        self.defense_time = False
        self.night_results = []

    def reset(self):
        self.__init__()

    def add_player(self, user):
        if len(self.players) < 5 and not any(p.user.id == user.id for p in self.players):
            player = Player(user)
            self.players.append(player)
            return True
        return False

    def assign_roles(self):
        random.shuffle(self.roles)
        for player in self.players:
            player.role = self.roles[self.players.index(player)]
            self.player_roles[player.user.id] = player.role

    def get_player_by_id(self, user_id):
        return next((p for p in self.players if p.user.id == user_id), None)

    def get_player_names(self):
        return [p.user.first_name for p in self.players if p.is_alive]

    def can_chat(self, user_id):
        player = self.get_player_by_id(user_id)
        if not player or not player.is_alive:
            return False
        if self.defense_time and player != self.defender:
            return False
        if self.chat_lock:
            return False
        return self.is_day and player.can_chat

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not global_game.is_started:
        keyboard = [[InlineKeyboardButton("پیوستن به بازی 🎮", callback_data='join_game')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "🎭 بازی مافیا (5 نفره)\n\nبازیکنان:\n"
        for i, player in enumerate(global_game.players, 1):
            message += f"{i}. {player.user.first_name}\n"
        message += f"\nتعداد بازیکنان: {len(global_game.players)}/5"
        sent_message = await update.message.reply_text(message, reply_markup=reply_markup)
        context.chat_data['main_message'] = sent_message

async def broadcast_to_players(context: ContextTypes.DEFAULT_TYPE, message: str, exclude_user_id=None, include_sender=True):
    for player in global_game.players:
        if exclude_user_id and player.user.id == exclude_user_id and not include_sender:
            continue
        try:
            await context.bot.send_message(chat_id=player.user.id, text=message)
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not global_game or not global_game.is_started:
        return
    
    user_id = update.message.from_user.id
    if not global_game.can_chat(user_id):
        return
        
    message = f"{update.message.from_user.first_name}: {update.message.text}"
    await broadcast_to_players(context, message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'join_game':
        if global_game.add_player(query.from_user):
            message = "🎭 بازی مافیا (5 نفره)\n\nبازیکنان:\n"
            for i, player in enumerate(global_game.players, 1):
                message += f"{i}. {player.user.first_name}\n"
            message += f"\nتعداد بازیکنان: {len(global_game.players)}/5"
            
            keyboard = [[InlineKeyboardButton("پیوستن به بازی 🎮", callback_data='join_game')]]
            if len(global_game.players) == 5:
                keyboard.append([InlineKeyboardButton("شروع بازی 🎯", callback_data='start_game')])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=message, reply_markup=reply_markup)

            if len(global_game.players) == 5:
                await broadcast_to_players(context, "بازی آماده شروع است!")

    elif query.data == 'start_game':
        if len(global_game.players) == 5 and not global_game.is_started:
            global_game.is_started = True
            global_game.assign_roles()
            
            # ارسال نقش‌ها به بازیکنان
            for player in global_game.players:
                role_message = f"نقش شما: {player.role}"
                try:
                    await context.bot.send_message(chat_id=player.user.id, text=role_message)
                except Exception as e:
                    logger.error(f"Error sending role to player: {e}")
            
            await broadcast_to_players(context, "بازی شروع شد! نقش‌ها به صورت خصوصی ارسال شد.")
            # شروع روز اول
            global_game.is_day = True
            global_game.day_count = 1
            await broadcast_to_players(context, "🌅 روز اول آغاز شد. می‌توانید شروع به گفتگو کنید.")

async def check_game_end():
    mafia_count = len([p for p in global_game.players if p.is_alive and p.role == "پدرخوانده🚬"])
    citizen_count = len([p for p in global_game.players if p.is_alive and p.role != "پدرخوانده🚬"])
    
    if mafia_count == 0:
        await broadcast_to_players(None, "🎉 شهروندان پیروز شدند!")
        global_game.reset()
        return True
    elif mafia_count >= citizen_count:
        await broadcast_to_players(None, "🎭 مافیا پیروز شد!")
        global_game.reset()
        return True
    return False

@app.get("/")
async def root():
    return {"status": "running"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_webhook():
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    global global_game
    global_game = GameRoom()
    
    await application.initialize()
    await setup_webhook()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot stopped")

application = ApplicationBuilder().token(TOKEN).build()