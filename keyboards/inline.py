from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def role_selection_keyboard():
    """Выбор роли при нажатии кнопки 'Контент'"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Я владелец канала", callback_data="role:owner")
    builder.button(text="👨‍💻 Я админ канала", callback_data="role:admin")
    builder.adjust(1)
    return builder.as_markup()


def channels_keyboard(channels_list):
    """Список каналов, полученный из БД (уже отфильтрованный по роли)"""
    builder = InlineKeyboardBuilder()

    for title, cid in channels_list:
        builder.button(text=str(title), callback_data=f"chan:{cid}")

    # Кнопка возврата к выбору роли
    builder.button(text="⬅️ Назад", callback_data="back_to_roles")
    builder.adjust(1)
    return builder.as_markup()


def action_keyboard(is_owner: bool = False):
    """Меню действий после выбора конкретного канала"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Текст", callback_data="action_text")
    builder.button(text="🖼 Фото/Видео", callback_data="add_media")
    builder.button(text="🎵 Аудио", callback_data="add_audio")

    # Кнопку обновления показываем всем, но в хендлере проверим права
    # Или можно скрыть: if is_owner: builder.button(...)
    builder.button(text="🔄 Обновить админов", callback_data="refresh_admins")

    builder.button(text="❌ Сбросить", callback_data="reset")

    builder.adjust(1, 2, 1, 1)  # Сетка: 1 кнопка, потом 2 в ряд, потом по 1
    return builder.as_markup()


def post_options_keyboard():
    """Меню после того, как текст уже введен"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🖼 Фото/Видео", callback_data="add_media")
    builder.button(text="🎵 Аудио", callback_data="add_audio")
    builder.button(text="🚀 Опубликовать", callback_data="publish")
    builder.button(text="❌ Сбросить", callback_data="reset")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def media_received_keyboard():
    """Клавиатура в процессе загрузки файлов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Опубликовать", callback_data="publish")
    builder.button(text="❌ Сбросить", callback_data="reset")
    builder.adjust(1)
    return builder.as_markup()


def back_to_roles_keyboard():
    """Простая кнопка назад, если список каналов пуст"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к выбору роли", callback_data="back_to_roles")
    return builder.as_markup()