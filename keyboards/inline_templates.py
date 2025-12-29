from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def start_template_kb():
    """Клавиатура начала: кнопка Старт и Отмена"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Начать создание", callback_data="tpl_start")
    builder.button(text="❌ Отмена", callback_data="tpl_cancel")
    builder.adjust(1)
    return builder.as_markup()

def step_controls_kb():
    """Клавиатура для каждого шага: Пропустить и Отмена"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data="tpl_skip")
    builder.button(text="❌ Отмена", callback_data="tpl_cancel")
    builder.adjust(2)
    return builder.as_markup()