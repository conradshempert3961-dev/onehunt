from aiogram.fsm.state import State, StatesGroup


class AppStates(StatesGroup):
    waiting_promo_code = State()
    waiting_broadcast_text = State()
    waiting_broadcast_premium_text = State()
