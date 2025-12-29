from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.filters import StateFilter
from states.post_states import PostCreator
from keyboards import inline, reply
from utils.db import db
from config import TG_EMOJI
import html
import logging

router = Router()


# --- 1. ВХОД В РАЗДЕЛ КОНТЕНТ (ВЫБОР РОЛИ) ---

@router.message(F.text == "Контент")
async def start_content(message: types.Message, state: FSMContext):
    await state.set_state(PostCreator.selecting_role)
    await message.answer(
        "👋 <b>Управление контентом</b>\n\nВыберите вашу роль в канале:",
        reply_markup=inline.role_selection_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_roles")
async def back_to_roles_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostCreator.selecting_role)
    await callback.message.edit_text(
        "👋 Выберите вашу роль:",
        reply_markup=inline.role_selection_keyboard()
    )


# --- 2. ВЫБОР КАНАЛА ---

@router.callback_query(PostCreator.selecting_role, F.data.startswith("role:"))
async def role_selected(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split(":")[1]  # Получаем "owner" или "admin"
    user_id = callback.from_user.id

    # СТРОГАЯ ФИЛЬТРАЦИЯ: теперь метод вернет только подходящие каналы
    user_channels = db.get_user_channels(user_id, role=role)

    if role == "owner":
        text_prefix = "👑 <b>Ваши собственные каналы!</b>"
        empty_msg = "У вас нет каналов, где вы являетесь Владельцем."
    else:
        text_prefix = "👨‍💻 <b>Каналы, где вы Администратор:</b>"
        empty_msg = "Список каналов, где вы назначены админом, пуст."

    if not user_channels:
        await callback.message.edit_text(
            f"❌ <b>{empty_msg}</b>\n\n"
            "Если вы владелец — добавьте бота в канал.\n"
            "Если вы админ — попросите владельца нажать 'Обновить админов' в его меню.",
            reply_markup=inline.back_to_roles_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.set_state(PostCreator.selecting_channel)
    await callback.message.edit_text(
        f"{text_prefix}\nВыберите канал для работы:",
        reply_markup=inline.channels_keyboard(user_channels),
        parse_mode="HTML"
    )


@router.callback_query(PostCreator.selecting_channel, F.data.startswith("chan:"))
async def channel_selected(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    channel_id = callback.data.split(":")[1]
    user_id = callback.from_user.id

    # 1. Проверка прав и существования канала в реальном времени
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)

        # Проверяем, разрешено ли пользователю публиковать
        is_allowed = (member.status == "creator") or (
                member.status == "administrator" and member.can_post_messages
        )

        if not is_allowed:
            # Если пользователь больше не админ — удаляем только ЕГО право в БД
            db.remove_user_permission(user_id, channel_id)
            await callback.answer("❌ Ваши права в этом канале были отозваны.", show_alert=True)
            # Возвращаем пользователя к выбору роли, чтобы список обновился
            await back_to_roles_handler(callback, state)
            return

    except Exception as e:
        err_msg = str(e).lower()
        # ЕСЛИ КАНАЛ УДАЛЕН ИЛИ БОТА ВЫГНАЛИ (Chat not found / Forbidden)
        if "chat not found" in err_msg or "forbidden" in err_msg or "chat_id_invalid" in err_msg:
            db.delete_channel(channel_id)  # УДАЛЯЕМ КАНАЛ ИЗ БАЗЫ
            await callback.answer("❌ Канал больше не существует или бот был удален.\nСписок каналов обновлен.",
                                  show_alert=True)
            # Возвращаем пользователя в самое начало (выбор роли)
            await back_to_roles_handler(callback, state)
            return

        # Если произошла какая-то другая техническая ошибка
        await callback.answer(f"⚠️ Ошибка доступа: {e}", show_alert=True)
        return

    # 2. Формируем ссылку на канал (Публичный или Приватный)
    if str(channel_id).startswith("@"):
        channel_link = f"https://t.me/{channel_id[1:]}"
    else:
        clean_id = str(channel_id).replace("-100", "")
        channel_link = f"https://t.me/c/{clean_id}/1"

    # 3. Сохраняем данные в FSM
    await state.update_data(selected_channel=channel_id, media_list=[], post_mode=None)
    await state.set_state(PostCreator.choosing_action)

    # 4. Получаем данные из БД для интерфейса
    is_owner = db.is_user_owner(user_id, channel_id)
    title = html.escape(db.get_channel_title(channel_id))  # Экранируем название

    # 5. Выводим меню действий
    await callback.message.edit_text(
        f"✅ Канал выбран: <a href='{channel_link}'><b>{title}</b></a>\n"
        f"Что сделаем?",
        reply_markup=inline.action_keyboard(is_owner=is_owner),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# --- 3. ОБНОВЛЕНИЕ АДМИНОВ (ТОЛЬКО ДЛЯ ВЛАДЕЛЬЦЕВ) ---

@router.callback_query(F.data == "refresh_admins")
async def refresh_admins(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    cid = data.get("selected_channel")
    user_id = callback.from_user.id

    if not db.is_user_owner(user_id, cid):
        await callback.answer("⛔️ Только владелец может обновлять список админов.", show_alert=True)
        return

    try:
        admins = await bot.get_chat_administrators(cid)
        chat = await bot.get_chat(cid)

        admins_to_sync = []
        for a in admins:
            is_creator = a.status == "creator"
            if is_creator or getattr(a, 'can_post_messages', False):
                admins_to_sync.append({
                    'id': a.user.id,
                    'username': a.user.username or a.user.first_name,
                    'is_owner': is_creator
                })

        db.sync_channel_admins(cid, chat.title, admins_to_sync)
        await callback.answer("✅ Список администраторов синхронизирован!", show_alert=True)

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# --- 4. СОЗДАНИЕ КОНТЕНТА (ТЕКСТ И МЕДИА) ---

@router.callback_query(F.data == "action_text")
async def ask_text(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostCreator.waiting_for_text)
    await callback.message.edit_text("✍️ <b>Отправьте текст для поста:</b>\n<i>(Поддерживается HTML-оформление)</i>",
                                     parse_mode="HTML")


@router.message(PostCreator.waiting_for_text)
async def receive_text(message: types.Message, state: FSMContext):
    # Логика определения HTML (оставляем как есть)
    if "<" in message.text and ">" in message.text:
        post_text, is_html = message.text, True
    elif message.html_text != message.text:
        post_text, is_html = message.html_text, True
    else:
        post_text, is_html = message.text, False

    # Отправляем сообщение с кнопками
    msg = await message.answer(
        f"{'✅ Шаблон/HTML принят.' if is_html else '📝 Текст принят.'}\n\n"
        f"Теперь вы можете прикрепить медиафайлы или нажать 'Опубликовать'.",
        reply_markup=inline.post_options_keyboard(),
        parse_mode="HTML"
    )

    # Сохраняем ID этого сообщения, чтобы удалить его, когда начнем слать медиа
    await state.update_data(post_text=post_text, is_html=is_html, last_msg_id=msg.message_id)
    await state.set_state(PostCreator.confirmation)


@router.callback_query(F.data.in_(["add_media", "add_audio"]))
async def add_files_mode(callback: types.CallbackQuery, state: FSMContext):
    mode = "media" if callback.data == "add_media" else "audio"
    await state.update_data(post_mode=mode)
    await state.set_state(PostCreator.waiting_for_media)

    text = "🖼 Присылайте <b>фото или видео</b> (по 1му до 10 шт):" if mode == "media" else "🎵 Присылайте <b>MP3-файлы</b> (по 1му до 10 шт):"
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(PostCreator.waiting_for_media, F.photo | F.video | F.audio | F.animation)
async def collect_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_list = data.get("media_list", [])
    mode = data.get("post_mode")

    if len(media_list) >= 10:
        await message.answer("⚠️ Лимит 10 файлов исчерпан!")
        return

    # Валидация типов
    if mode == "audio" and not message.audio:
        return await message.answer("❌ В этом режиме принимаются только аудио.")
    if mode == "media" and message.audio:
        return await message.answer("❌ В этом режиме принимаются только фото/видео.")

    # Получаем file_id
    if message.photo:
        fid, ftype = message.photo[-1].file_id, "photo"
    elif message.video:
        fid, ftype = message.video.file_id, "video"
    elif message.animation:
        fid, ftype = message.animation.file_id, "video"
    elif message.audio:
        fid, ftype = message.audio.file_id, "audio"

    media_list.append({"id": fid, "type": ftype})
    await state.update_data(media_list=media_list)

    await message.answer(f"✅ Файл {len(media_list)}/10 добавлен.", reply_markup=inline.media_received_keyboard())


# --- 5. ФИНАЛЬНАЯ ПУБЛИКАЦИЯ ---

@router.callback_query(F.data == "publish")
async def publish_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    cid = data.get("selected_channel")

    # 1. Проверка сессии
    if not cid:
        await callback.answer("⚠️ Сессия истекла или пост уже опубликован.")
        try:
            await callback.message.delete()
        except:
            pass
        return

    # 2. Подготовка данных
    text = data.get("post_text", "")
    is_html = data.get("is_html", False)
    media_list = data.get("media_list", [])

    # Экранируем название канала, чтобы знаки вроде & или < в названии не ломали HTML-ссылку
    title = html.escape(db.get_channel_title(cid))

    # Формируем ссылки для футера
    clean_id = str(cid).replace("-100", "")
    link = f"https://t.me/{cid[1:]}" if str(cid).startswith("@") else f"https://t.me/c/{clean_id}/1"

    # Варианты футеров
    footer_rich = f"\n\n{TG_EMOJI} <a href='{link}'>{title}</a>"
    footer_plain = f"\n\n⛺️ <a href='{link}'>{title}</a>"

    # 3. Внутренняя функция отправки (с поддержкой альбомов и parse_mode)
    async def send_to_tg(caption, parse_mode="HTML"):
        if not media_list:
            await bot.send_message(cid, text=caption, parse_mode=parse_mode)
        elif len(media_list) == 1:
            m = media_list[0]
            if m['type'] == "photo":
                await bot.send_photo(cid, m['id'], caption=caption, parse_mode=parse_mode)
            elif m['type'] == "video":
                await bot.send_video(cid, m['id'], caption=caption, parse_mode=parse_mode)
            elif m['type'] == "audio":
                await bot.send_audio(cid, m['id'], caption=caption, parse_mode=parse_mode)
        else:
            album_builder = MediaGroupBuilder(caption=caption)
            for m in media_list:
                if m['type'] == "photo":
                    album_builder.add_photo(media=m['id'])
                elif m['type'] == "video":
                    album_builder.add_video(media=m['id'])
                elif m['type'] == "audio":
                    album_builder.add_audio(media=m['id'])

            media_group = album_builder.build()
            if media_group:
                # Принудительно ставим режим парсинга первому элементу альбома
                media_group[0].parse_mode = parse_mode

            await bot.send_media_group(cid, media=media_group)

    # 4. Основная логика публикации
    try:
        if is_html:
            # СЦЕНАРИЙ: ШАБЛОН (без футера)
            try:
                await send_to_tg(text, parse_mode="HTML")
                await callback.message.edit_text("🚀 <b>Опубликовано!</b> (Шаблон)", parse_mode="HTML")
            except Exception:
                # Если в шаблоне критическая ошибка синтаксиса, шлем как голый текст
                await send_to_tg(text, parse_mode=None)
                await callback.message.edit_text("⚠️ <b>Опубликовано без оформления</b> (ошибка в тегах).",
                                                 parse_mode="HTML")
        else:
            # СЦЕНАРИЙ: ОБЫЧНЫЙ ТЕКСТ (с футером)
            try:
                # Попытка 1: Идеальный вариант (HTML + Кастомный эмодзи)
                await send_to_tg(f"{text}{footer_rich}", parse_mode="HTML")
                await callback.message.edit_text("🚀 <b>Опубликовано с футером!</b>", parse_mode="HTML")
            except Exception as e:
                err_str = str(e).lower()
                # Если проблема в эмодзи (бусты) или простом HTML
                if "entities" in err_str or "custom emoji" in err_str or "can't parse" in err_str:
                    try:
                        # Попытка 2: Обычный эмодзи, но всё еще HTML
                        await send_to_tg(f"{text}{footer_plain}", parse_mode="HTML")
                        await callback.message.edit_text("🚀 <b>Опубликовано!</b> (Заменен эмодзи)", parse_mode="HTML")
                    except:
                        # Попытка 3: "Умный Fallback"
                        # Если в тексте есть знаки < или >, которые ломают HTML,
                        # мы экранируем ТЕКСТ, но оставляем ФУТЕР кликабельным (в HTML режиме)
                        safe_text = html.escape(text)
                        await send_to_tg(f"{safe_text}{footer_plain}", parse_mode="HTML")
                        await callback.message.edit_text(
                            "⚠️ <b>Опубликовано</b> (Текст экранирован, ссылка сохранена).", parse_mode="HTML")
                else:
                    raise e

    except Exception as e:
        await callback.message.answer(f"❌ Критическая ошибка: {e}")
    finally:
        await state.clear()


# --- 6. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

@router.callback_query(F.data == "reset")
async def reset_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("🔄 Действие отменено.", reply_markup=reply.main_menu())


@router.message(F.entities, StateFilter(None))
async def get_emoji_info(message: types.Message):
    """Помощник для получения ID кастомных эмодзи"""
    for entity in message.entities:
        if entity.type == "custom_emoji":
            await message.answer(f"ID эмодзи для <code>config.py</code>:\n<code>{entity.custom_emoji_id}</code>",
                                 parse_mode="HTML")