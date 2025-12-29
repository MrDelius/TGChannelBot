from aiogram.fsm.state import State, StatesGroup


class PostCreator(StatesGroup):
    # 1. Выбор роли (Владелец или Админ)
    selecting_role = State()

    # 2. Выбор канала из списка доступных
    selecting_channel = State()

    # 3. Главное меню работы с каналом (Текст, Медиа, Обновить админов)
    choosing_action = State()

    # 4. Ожидание ввода текста поста
    waiting_for_text = State()

    # 5. Ожидание отправки файлов (Фото/Видео/Аудио)
    waiting_for_media = State()

    # 6. Состояние подтверждения (меню перед публикацией)
    confirmation = State()