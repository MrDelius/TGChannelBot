from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    """Главное меню бота с основными разделами"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Контент")],
            [KeyboardButton(text="Шаблоны")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите нужный раздел..."
    )