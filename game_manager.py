from typing import Dict, List, Optional
import asyncio
import random
from player import Player
from messages import Messages
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

class GameManager:
    def __init__(self):
        self.games: Dict[int, 'Game'] = {}
        self.waiting_players: Dict[int, Player] = {}
        
    async def handle_start_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name
        
        if len(self.waiting_players) >= 8:
            await update.message.reply_text("بازی پر است. لطفاً منتظر بمانید.")
            return
            
        if user_id not in self.waiting_players:
            player = Player(user_id, username)
            self.waiting_players[user_id] = player
            
            player_list = ["‏{}. ‏{}".format(i+1, p.username if i < len(self.waiting_players) else "") 
                          for i in range(8)]
            
            waiting_message = Messages.GAME_START.format("\n".join(player_list))
            
            for p in self.waiting_players.values():
                try:
                    await context.bot.send_message(
                        chat_id=p.user_id,
                        text=waiting_message
                    )
                    if p.user_id != user_id:
                        await context.bot.send_message(
                            chat_id=p.user_id,
                            text=Messages.PLAYER_JOINED.format(len(self.waiting_players), username)
                        )
                except Exception as e:
                    print(f"Error sending message to {p.username}: {e}")
            
            if len(self.waiting_players) == 8:
                await self.start_new_game(context)

    async def start_new_game(self, context: ContextTypes.DEFAULT_TYPE):
        game = Game(list(self.waiting_players.values()))
        game_id = random.randint(1000, 9999)
        self.games[game_id] = game
        self.waiting_players.clear()
        
        await game.start_game(context)

class Game:
    def __init__(self, players: List[Player]):
        self.players = players
        self.current_phase = "night"
        self.day_count = 1
        self.night_count = 1
        self.is_voting = False
        self.defense_player = None
        self.final_voting = False
        
        self.roles = [
            "godfather", "minion", "mafia", "mafia",
            "citizen", "citizen", "citizen", "citizen"
        ]
        random.shuffle(self.roles)
        
        for player, role in zip(self.players, self.roles):
            player.assign_role(role)

    async def start_game(self, context: ContextTypes.DEFAULT_TYPE):
        for player in self.players:
            team_emoji = "🔴" if player.team == "mafia" else "🟢"
            role_description = self.get_role_description(player.role)
            
            message = Messages.ROLE_ASSIGN.format(
                player.role,
                team_emoji + " " + player.team.capitalize(),
                role_description
            )
            
            try:
                await context.bot.send_message(
                    chat_id=player.user_id,
                    text=message
                )
            except Exception as e:
                print(f"Error sending role to {player.username}: {e}")
        
        await asyncio.sleep(25)
        await self.start_night_phase(context)

    def get_role_description(self, role: str) -> str:
        descriptions = {
            "godfather": "میتوانید در شب بکشید و رهبر مافیا هستید.",
            "minion": "عضو تیم مافیا هستید و در صورت مرگ گادفادر می‌توانید بکشید.",
            "mafia": "عضو تیم مافیا هستید.",
            "citizen": "میتوانید در روز به مافیا رای دهید."
        }
        return descriptions.get(role, "")

    async def start_night_phase(self, context: ContextTypes.DEFAULT_TYPE):
        self.current_phase = "night"
        
        night_message = Messages.NIGHT_START.format(self.night_count)
        for player in self.players:
            if player.is_alive:
                try:
                    keyboard = None
                    if player.can_kill():
                        targets = [[InlineKeyboardButton(p.username, callback_data=f"kill_{p.user_id}")] 
                                 for p in self.players if p.is_alive and p.user_id != player.user_id]
                        keyboard = InlineKeyboardMarkup(targets)
                    
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text=night_message,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    print(f"Error in night phase for {player.username}: {e}")
        
        await asyncio.sleep(30)
        await self.start_day_phase(context)

    async def handle_night_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        action, target_id = query.data.split('_')
        player = self.get_player_by_id(int(query.from_user.id))
        target = self.get_player_by_id(int(target_id))
        
        if action == "kill" and player and target:
            target.marked_for_death = True
            await query.answer("هدف انتخاب شد!")
            await context.bot.edit_message_reply_markup(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                reply_markup=None
            )

    async def start_day_phase(self, context: ContextTypes.DEFAULT_TYPE):
        self.current_phase = "day"
        self.process_night_actions()
        
        status_message = self.get_game_status()
        for player in self.players:
            if player.is_alive:
                try:
                    keyboard = [[InlineKeyboardButton(p.username, callback_data=f"vote_{p.user_id}")] 
                              for p in self.players if p.is_alive and p.user_id != player.user_id]
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text=status_message,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    print(f"Error in day phase for {player.username}: {e}")

    def process_night_actions(self):
        for player in self.players:
            if player.marked_for_death:
                player.is_alive = False
                player.marked_for_death = False

    def get_game_status(self) -> str:
        alive_players = [p for p in self.players if p.is_alive]
        dead_players = [p for p in self.players if not p.is_alive]
        
        status = f"روز {self.day_count}\n\n"
        status += "بازیکنان زنده:\n"
        for i, player in enumerate(alive_players, 1):
            status += f"{i}. {player.username}\n"
        
        if dead_players:
            status += "\nبازیکنان مرده:\n"
            for i, player in enumerate(dead_players, 1):
                status += f"{i}. {player.username}\n"
        
        return status

    def get_player_by_id(self, user_id: int) -> Optional[Player]:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def check_game_end(self) -> Optional[str]:
        alive_mafia = sum(1 for p in self.players if p.is_alive and p.team == "mafia")
        alive_citizens = sum(1 for p in self.players if p.is_alive and p.team == "citizen")
        
        if alive_mafia == 0:
            return "citizen"
        elif alive_mafia >= alive_citizens:
            return "mafia"
        return None