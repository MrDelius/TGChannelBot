from aiogram import Router, types, Bot, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER, ADMINISTRATOR, MEMBER
from keyboards.reply import main_menu
from utils.db import db
from config import ADMIN_ID
import asyncio
import html

router = Router()


def get_channel_link(chat_id: int, chat_username: str = None) -> str:
    if chat_username:
        return f"https://t.me/{chat_username}"
    clean_id = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{clean_id}/1"


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветствие и выдача главного меню"""
    # Если вы хотите оставить бота публичным, убираем проверку на ADMIN_ID.
    # Если бот только для вас и ваших друзей, можно оставить проверку.
    await message.answer(
        "👋 Привет! Я помогу тебе управлять контентом в Telegram-каналах.\n\n"
        "<b>Как начать:</b>\n"
        "1. Добавь меня в свой канал.\n"
        "2. Сделай администратором с правом <b>'Публикация сообщений'</b>.\n"
        "3. Нажми кнопку 'Контент' ниже.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=(IS_NOT_MEMBER | MEMBER) >> ADMINISTRATOR))
async def bot_added_as_admin(event: types.ChatMemberUpdated, bot: Bot):
    await asyncio.sleep(1)
    """Срабатывает при добавлении бота в админы"""
    chat_id = event.chat.id
    chat_title = html.escape(event.chat.title)
    chat_url = get_channel_link(chat_id, event.chat.username)

    actor = event.from_user  # Тот, кто добавил бота

    try:
        admins = await bot.get_chat_administrators(chat_id)
        admins_to_sync = []
        owner_id = None

        for admin in admins:
            is_creator = admin.status == "creator"
            if is_creator: owner_id = admin.user.id

            can_post = is_creator or getattr(admin, 'can_post_messages', False)
            if can_post:
                admins_to_sync.append({
                    'id': admin.user.id,
                    'username': admin.user.username or admin.user.first_name or "User",
                    'is_owner': is_creator
                })

        # Синхронизируем базу
        db.sync_channel_admins(chat_id, chat_title, admins_to_sync)

        # ФОРМИРУЕМ УВЕДОМЛЕНИЯ
        msg_for_owner = f"➕ <b>Бот подключен к вашему каналу!</b>\nКанал: <a href='{chat_url}'>{chat_title}</a>"
        if actor.id != owner_id:
            msg_for_owner += f"\nДобавил: @{actor.username or actor.id}"

        # Отправляем владельцу канала
        if owner_id:
            try:
                await bot.send_message(owner_id, msg_for_owner, disable_web_page_preview=True)
            except:
                pass

        # Отправляем тому, кто добавил (если это не владелец)
        if actor.id != owner_id:
            try:
                await bot.send_message(
                    actor.id,
                    f"✅ Вы успешно подключили боту канал <a href='{chat_url}'>{chat_title}</a>.",
                    disable_web_page_preview=True
                )
            except:
                pass

    except Exception as e:
        print(f"Error in bot_added: {e}")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=ADMINISTRATOR >> (IS_NOT_MEMBER | MEMBER)))
async def bot_removed_from_admin(event: types.ChatMemberUpdated, bot: Bot):
    """Срабатывает при удалении бота"""
    chat_id = event.chat.id
    chat_title = html.escape(event.chat.title)
    chat_url = get_channel_link(chat_id, event.chat.username)

    actor = event.from_user  # Тот, кто удалил

    # 1. Сначала узнаем из БД, кто был владельцем, пока данные не стерты
    owner_id = db.get_channel_owner_id(chat_id)

    # 2. Удаляем канал из БД
    db.delete_channel(chat_id)

    # 3. Отправляем уведомления
    msg_for_owner = f"❌ <b>Бот удален из вашего канала!</b>\nКанал: <a href='{chat_url}'>{chat_title}</a>"
    if owner_id and actor.id != owner_id:
        msg_for_owner += f"\nДействие совершил: @{actor.username or actor.id}"

    # Сообщение владельцу канала
    if owner_id:
        try:
            await bot.send_message(owner_id, msg_for_owner, disable_web_page_preview=True)
        except:
            pass

    # Сообщение тому, кто удалил (если это не владелец)
    if actor.id != owner_id:
        try:
            await bot.send_message(
                actor.id,
                f"❌ Вы удалили бота из канала <a href='{chat_url}'>{chat_title}</a>.",
                disable_web_page_preview=True
            )
        except:
            pass


@router.message(Command("info"))
async def cmd_info(message: types.Message):
    """Подробная инструкция по использованию бота"""
    info_text = (
        "ℹ️ <b>Инструкция по использованию бота</b>\n\n"
        "1️⃣ <b>Публикация контента:</b>\n"
        "• Нажмите кнопку <b>'Контент'</b>.\n"
        "• Выберите вашу роль (Владелец/Админ) — это ваши каналы или каналы, где вы являетесь админом.\n"
        "• Выберите канал из списка (бот проверит ваши права в реальном времени).\n"
        "• Отправьте текст поста (можно использовать HTML-теги).\n"
        "• Добавьте медиафайлы (Фото, Видео, Аудио) — по 1му до 10 штук.\n"
        "• Нажмите <b>'Опубликовать'</b>.\n\n"

        "2️⃣ <b>Конструктор шаблонов:</b>\n"
        "Этот раздел поможет создать идеально оформленный текст. "
        "Создание проходит в <b>7 этапов</b>:\n"
        "1. Название (Заголовок)\n"
        "2. Подзаголовок\n"
        "3. Основная часть текста\n"
        "4. Заметка (выделяется как цитата)\n"
        "5. Заключение\n"
        "6. Хештеги\n"
        "7. Ссылки\n\n"

        "💡 <b>Совет:</b> После завершения шаблона вы получите готовый код. "
        "Просто нажмите на него, чтобы скопировать, и вставьте в разделе 'Контент'.\n\n"

        "⚠️ <b>Премиум-эмодзи:</b> Будут отображаться в канале только при наличии <b>Boost 2-го уровня</b>."
    )
    await message.answer(info_text, parse_mode="HTML")