from aiogram.fsm.state import State, StatesGroup

class AddFilm(StatesGroup):
    code = State()
    title = State()

class DeleteFilm(StatesGroup):
    code = State()

class AddPart(StatesGroup):
    movie_code = State()
    title = State()
    description = State()
    video = State()

class Broadcast(StatesGroup):
    message = State()
