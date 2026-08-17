from aiogram.fsm.state import State, StatesGroup


class Booking(StatesGroup):
    service = State()
    master = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    note = State()
    confirm = State()

