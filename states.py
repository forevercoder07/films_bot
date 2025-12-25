from aiogram.fsm.state import StatesGroup, State

class AddFilm(StatesGroup):
    code = State()
    title = State()

class DeleteFilm(StatesGroup):
    code = State()

class AddPart(StatesGroup):
    # Bu state’lar "Add film part" tugmasi uchun
    movie_code = State()   # Film kodini kiritish
    title = State()        # Qism nomini kiritish
    video = State()        # Qism videosini yuborish

class Broadcast(StatesGroup):
    message = State()

class SearchStates(StatesGroup):
    waiting_code = State()
    waiting_part_selection = State()

class AddAdminStates(StatesGroup):
    waiting_admin_id = State()
    waiting_permissions = State()
