from aiogram.fsm.state import State, StatesGroup

class TemplateCreator(StatesGroup):
    waiting_for_title = State()      # Название
    waiting_for_subtitle = State()   # Подзаголовок
    waiting_for_body = State()       # Основная часть
    waiting_for_note = State()       # Заметка
    waiting_for_conclusion = State() # Заключение
    waiting_for_hashtags = State()   # Хештеги
    waiting_for_links = State()      # Ссылки