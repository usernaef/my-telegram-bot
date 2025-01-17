class Player:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.role = None
        self.team = None
        self.is_alive = True
        self.marked_for_death = False
        self.votes = 0

    def assign_role(self, role: str):
        self.role = role
        self.team = "mafia" if role in ["godfather", "minion", "mafia"] else "citizen"

    def can_kill(self) -> bool:
        return (self.role == "godfather" or 
                (self.role == "minion" and 
                 not any(p for p in self.game.players 
                        if p.role == "godfather" and p.is_alive)))