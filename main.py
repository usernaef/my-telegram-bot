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
from datetime import datetime, timedelta

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
        self.phase = "pre_game"  # pre_game, introduction, day, voting, defense, final_vote, night
        self.chat_enabled = False
        self.night_actions = {}
        self.voting_in_progress = False
        self.votes = {}
        self.doctor_save = None
        self.mafia_kill = None
        self.defense_mode = False
        self.defender = None
        self.defense_votes = {}
        self.final_voting = False
        self.phase_end_time = None
        self.night_results = []

    async def start_introduction_phase(self, context):
        self.phase = "introduction"
        self.chat_enabled = True
        self.phase_end_time = datetime.now() + timedelta(seconds=20)
        await broadcast_to_players(context, "🎭 مرحله آشنایی شروع شد - ۲۰ ثانیه فرصت دارید")
        await asyncio.sleep(20)
        await self.start_night_phase(context)

    async def start_night_phase(self, context):
        self.phase = "night"
        self.chat_enabled = False
        self.is_day = False
        self.phase_end_time = datetime.now() + timedelta(seconds=30)
        await broadcast_to_players(context, "🌙 شب شد - نقش‌های شب در حال انجام وظایف خود هستند")
        await asyncio.sleep(30)
        await self.start_day_phase(context)

    async def start_day_phase(self, context):
        self.phase = "day"
        self.chat_enabled = True
        self.is_day = True
        self.day_count += 1
        self.phase_end_time = datetime.now() + timedelta(seconds=120)
        await broadcast_to_players(context, f"🌅 روز {self.day_count} شروع شد")
        await asyncio.sleep(120)
        await self.start_voting_phase(context)

    async def start_voting_phase(self, context):
        self.phase = "voting"
        self.voting_in_progress = True
        self.votes = {}
        keyboard = []
        for player in [p for p in self.players if p.is_alive]:
            keyboard.append([InlineKeyboardButton(player.user.first_name, callback_data=f'vote_{player.user.id}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await broadcast_to_players(context, "🗳️ زمان رای‌گیری رسید", reply_markup=reply_markup)

    async def start_defense_phase(self, context, defender):
        self.phase = "defense"
        self.defender = defender
        self.chat_enabled = True
        self.phase_end_time = datetime.now() + timedelta(seconds=15)
        await broadcast_to_players(context, f"⚖️ {defender.user.first_name} در حال دفاع است - ۱۵ ثانیه فرصت دارد")
        await asyncio.sleep(15)
        await self.start_final_vote_phase(context)

    async def start_final_vote_phase(self, context):
        self.phase = "final_vote"
        keyboard = [
            [InlineKeyboardButton("گناهکار ⚰️", callback_data='guilty')],
            [InlineKeyboardButton("بی‌گناه 😇", callback_data='innocent')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await broadcast_to_players(context, "🎯 رای نهایی خود را اعلام کنید", reply_markup=reply_markup)

    def can_chat(self, user_id):
        if not self.chat_enabled:
            return False
        player = self.get_player_by_id(user_id)
        if not player or not player.is_alive:
            return False
        if self.phase == "defense" and player != self.defender:
            return False
        return True

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

async def broadcast_to_players(context: ContextTypes.DEFAULT_TYPE, message: str, reply_markup=None, exclude_user_id=None):
    for player in global_game.players:
        if exclude_user_id and player.user.id == exclude_user_id:
            continue
        try:
            await context.bot.send_message(
                chat_id=player.user.id,
                text=message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")

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

    elif query.data == 'start_game':
        if len(global_game.players) == 5 and not global_game.is_started:
            global_game.is_started = True
            global_game.assign_roles()
            
            for player in global_game.players:
                role_message = f"نقش شما: {player.role}"
                await context.bot.send_message(chat_id=player.user.id, text=role_message)
            
            await broadcast_to_players(context, "بازی شروع شد! نقش‌ها به صورت خصوصی ارسال شد.")
            await global_game.start_introduction_phase(context)

    elif query.data.startswith('vote_'):
        if global_game.phase == "voting":
            target_id = int(query.data.split('_')[1])
            voter = global_game.get_player_by_id(query.from_user.id)
            if voter and voter.is_alive and not voter.has_voted:
                target = global_game.get_player_by_id(target_id)
                if target and target.is_alive:
                    voter.has_voted = True
                    target.votes += 1
                    await query.edit_message_text(f"شما به {target.user.first_name} رای دادید")

    elif query.data in ['guilty', 'innocent']:
        if global_game.phase == "final_vote":
            voter = global_game.get_player_by_id(query.from_user.id)
            if voter and voter.is_alive and voter.user.id not in global_game.defense_votes:
                global_game.defense_votes[voter.user.id] = query.data
                await query.edit_message_text("رای شما ثبت شد")

async def setup_webhook():
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    global global_game, application
    global_game = GameRoom()
    
    application = ApplicationBuilder().token(TOKEN).build()
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

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "running"}