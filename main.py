import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
import random
import logging
import asyncio

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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
async def start(update: Update, context):
    global global_game
    if global_game is None:
        global_game = GameRoom()
    
    if not global_game.is_started:
        if global_game.add_player(update.effective_user):
            await update.message.reply_text(f"بازیکن {update.effective_user.first_name} به بازی پیوست.\n"
                                         f"تعداد بازیکنان: {len(global_game.players)}/5")
            if len(global_game.players) == 5:
                global_game.assign_roles()
                global_game.is_started = True
                await announce_roles(context)
                await start_day(context)
        else:
            await update.message.reply_text("نمی‌توانید به بازی بپیوندید. یا بازی پر است یا قبلاً عضو شده‌اید.")
    else:
        await update.message.reply_text("بازی در حال انجام است. لطفاً منتظر بمانید تا این بازی تمام شود.")

async def announce_roles(context):
    for player in global_game.players:
        role_message = f"نقش شما: {player.role}"
        try:
            await context.bot.send_message(chat_id=player.user.id, text=role_message)
        except Exception as e:
            logger.error(f"Error sending role to {player.user.first_name}: {e}")

async def start_day(context):
    global global_game
    if not global_game:
        return

    global_game.day_count += 1
    global_game.is_day = True
    global_game.voting_in_progress = False
    global_game.votes.clear()
    global_game.night_actions.clear()
    global_game.chat_enabled = True
    global_game.defense_mode = False
    global_game.defender = None
    global_game.defense_votes.clear()
    global_game.final_voting = False
    global_game.chat_lock = False
    global_game.defense_time = False
    
    for player in global_game.players:
        if player.is_alive:
            player.has_voted = False
            player.has_used_ability = False
            player.votes = 0
            player.current_selection = None
            player.can_chat = True

    alive_players = [p for p in global_game.players if p.is_alive]
    day_message = f"☀️ روز {global_game.day_count} آغاز شد\n\n"
    day_message += "بازیکنان زنده:\n"
    for player in alive_players:
        day_message += f"- {player.user.first_name}\n"

    if global_game.night_results:
        day_message += "\nنتایج شب:\n"
        for result in global_game.night_results:
            day_message += f"- {result}\n"
        global_game.night_results.clear()

    for player in global_game.players:
        try:
            await context.bot.send_message(chat_id=player.user.id, text=day_message)
        except Exception as e:
            logger.error(f"Error sending day message to {player.user.first_name}: {e}")

    # Start voting after 2 minutes
    await asyncio.sleep(120)
    if global_game and global_game.is_day:
        await start_voting(context)

async def start_voting(context):
    global global_game
    if not global_game or not global_game.is_day:
        return

    global_game.voting_in_progress = True
    global_game.chat_enabled = False
    
    alive_players = [p for p in global_game.players if p.is_alive]
    keyboard = []
    for player in alive_players:
        keyboard.append([InlineKeyboardButton(player.user.first_name, callback_data=f"vote_{player.user.id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    voting_message = "🗳️ زمان رأی‌گیری فرا رسیده است!\nبه کسی که فکر می‌کنید مافیاست رأی دهید:"

    for player in global_game.players:
        if player.is_alive:
            try:
                msg = await context.bot.send_message(
                    chat_id=player.user.id,
                    text=voting_message,
                    reply_markup=reply_markup
                )
                player_messages[player.user.id] = msg.message_id
            except Exception as e:
                logger.error(f"Error sending voting message to {player.user.first_name}: {e}")

    # End voting after 1 minute
    await asyncio.sleep(60)
    if global_game and global_game.voting_in_progress:
        await end_voting(context)
async def end_voting(context):
    global global_game
    if not global_game:
        return

    global_game.voting_in_progress = False
    most_voted = None
    max_votes = 0
    
    for player in global_game.players:
        if player.is_alive and player.votes > max_votes:
            max_votes = player.votes
            most_voted = player

    if most_voted:
        global_game.defender = most_voted
        global_game.defense_time = True
        defense_message = f"👨‍⚖️ {most_voted.user.first_name} بیشترین رأی را آورده است.\n"
        defense_message += "لطفاً از خود دفاع کنید."

        keyboard = [[InlineKeyboardButton("موافق اعدام", callback_data="defense_yes"),
                    InlineKeyboardButton("مخالف اعدام", callback_data="defense_no")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for player in global_game.players:
            try:
                if player.user.id == most_voted.user.id:
                    await context.bot.send_message(chat_id=player.user.id, text="🎤 نوبت دفاع شماست!")
                else:
                    msg = await context.bot.send_message(
                        chat_id=player.user.id,
                        text=defense_message,
                        reply_markup=reply_markup
                    )
                    player_messages[player.user.id] = msg.message_id
            except Exception as e:
                logger.error(f"Error sending defense message to {player.user.first_name}: {e}")

        # End defense after 30 seconds
        await asyncio.sleep(30)
        if global_game and global_game.defense_time:
            await end_defense(context)

async def end_defense(context):
    global global_game
    if not global_game:
        return

    global_game.defense_time = False
    yes_votes = sum(1 for vote in global_game.defense_votes.values() if vote)
    no_votes = sum(1 for vote in global_game.defense_votes.values() if not vote)
    
    result_message = f"نتیجه رأی‌گیری نهایی:\n"
    result_message += f"موافق اعدام: {yes_votes}\n"
    result_message += f"مخالف اعدام: {no_votes}\n"

    if yes_votes > no_votes:
        global_game.defender.is_alive = False
        result_message += f"\n☠️ {global_game.defender.user.first_name} اعدام شد."
        result_message += f"\nنقش ایشان {global_game.defender.role} بود."
    else:
        result_message += f"\n😌 {global_game.defender.user.first_name} نجات یافت."

    for player in global_game.players:
        try:
            await context.bot.send_message(chat_id=player.user.id, text=result_message)
        except Exception as e:
            logger.error(f"Error sending result message to {player.user.first_name}: {e}")

    if check_game_end():
        await end_game(context)
    else:
        await start_night(context)

def check_game_end():
    global global_game
    if not global_game:
        return False

    mafia_count = sum(1 for p in global_game.players if p.is_alive and p.role == "Mafia")
    citizen_count = sum(1 for p in global_game.players if p.is_alive and p.role != "Mafia")

    return mafia_count >= citizen_count or mafia_count == 0

async def end_game(context):
    global global_game
    if not global_game:
        return

    mafia_count = sum(1 for p in global_game.players if p.is_alive and p.role == "Mafia")
    winner = "مافیا" if mafia_count > 0 else "شهروندان"
    
    end_message = f"🏁 بازی به پایان رسید!\n"
    end_message += f"برنده: {winner}\n\n"
    end_message += "نقش‌های بازیکنان:\n"
    for player in global_game.players:
        status = "زنده" if player.is_alive else "مرده"
        end_message += f"- {player.user.first_name}: {player.role} ({status})\n"

    for player in global_game.players:
        try:
            await context.bot.send_message(chat_id=player.user.id, text=end_message)
        except Exception as e:
            logger.error(f"Error sending end game message to {player.user.first_name}: {e}")

    global_game = None

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling()

if __name__ == "__main__":
    main()