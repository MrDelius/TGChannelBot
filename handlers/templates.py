import html
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from states.template_states import TemplateCreator
from keyboards import inline_templates as kb_tpl
from keyboards import reply

router = Router()


# --- ВХОД В ШАБЛОНЫ ---
@router.message(F.text == "Шаблоны")
async def start_template_info(message: types.Message, state: FSMContext):
    await state.clear()  # Сбрасываем старые состояния на всякий случай
    await message.answer(
        "📝 <b>Конструктор шаблона поста</b>\n\n"
        "Я помогу вам собрать структурированный текст для канала.\n\n"
        "⚠️ <b>ВАЖНО:</b> Если вы используете премиум-эмодзи, "
        "они будут видны в канале только при наличии <b>Boost 2 уровня</b>.\n\n"
        "Начать создание?",
        reply_markup=kb_tpl.start_template_kb(),
        parse_mode="HTML"
    )


# --- ОБРАБОТКА КНОПОК УПРАВЛЕНИЯ ---
@router.callback_query(F.data == "tpl_cancel")
async def cancel_tpl(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔄 Создание шаблона отменено.")
    await callback.message.answer("Главное меню:", reply_markup=reply.main_menu())


@router.callback_query(F.data == "tpl_start")
async def start_tpl_process(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TemplateCreator.waiting_for_title)
    await callback.message.edit_text("1️⃣ Введите <b>Название (Заголовок)</b> поста:",
                                     reply_markup=kb_tpl.step_controls_kb(),
                                     parse_mode="HTML")


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПЕРЕХОДА ---
async def next_step(message: types.Message, state: FSMContext, key: str, value: str, next_st: State, next_txt: str):
    # Проверка на наличие премиум-эмодзи в текущем сообщении
    has_premium = False
    if message and message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                has_premium = True

    data = await state.get_data()
    all_premium = data.get("has_premium", False) or has_premium

    await state.update_data({key: value, "has_premium": all_premium})
    await state.set_state(next_st)

    await message.answer(next_txt, reply_markup=kb_tpl.step_controls_kb(), parse_mode="HTML")


# --- ОБРАБОТКА КНОПКИ "ПРОПУСТИТЬ" ---
@router.callback_query(F.data == "tpl_skip")
async def skip_step(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()

    # Карта переходов
    steps = {
        TemplateCreator.waiting_for_title: (
        "t_title", TemplateCreator.waiting_for_subtitle, "2️⃣ Введите <b>Подзаголовок</b>:"),
        TemplateCreator.waiting_for_subtitle: (
        "t_subtitle", TemplateCreator.waiting_for_body, "3️⃣ Введите <b>Основной текст</b>:"),
        TemplateCreator.waiting_for_body: (
        "t_body", TemplateCreator.waiting_for_note, "4️⃣ Введите <b>Заметку</b> (цитата):"),
        TemplateCreator.waiting_for_note: (
        "t_note", TemplateCreator.waiting_for_conclusion, "5️⃣ Введите <b>Заключение</b>:"),
        TemplateCreator.waiting_for_conclusion: (
        "t_conclusion", TemplateCreator.waiting_for_hashtags, "6️⃣ Введите <b>Хештеги</b>:"),
        TemplateCreator.waiting_for_hashtags: (
        "t_hashtags", TemplateCreator.waiting_for_links, "7️⃣ Введите <b>Ссылки</b>:"),
    }

    if current_state in steps:
        key, nst, ntxt = steps[current_state]
        await callback.message.delete()
        await next_step(callback.message, state, key, "", nst, ntxt)
    elif current_state == TemplateCreator.waiting_for_links:
        await callback.message.delete()
        await finalize_template(callback.message, state, is_skip=True)


# --- ХЕНДЛЕРЫ ВВОДА ТЕКСТА ---
@router.message(TemplateCreator.waiting_for_title)
async def get_title(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_title", message.html_text, TemplateCreator.waiting_for_subtitle,
                    "2️⃣ Введите <b>Подзаголовок</b>:")


@router.message(TemplateCreator.waiting_for_subtitle)
async def get_subtitle(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_subtitle", message.html_text, TemplateCreator.waiting_for_body,
                    "3️⃣ Введите <b>Основной текст</b>:")


@router.message(TemplateCreator.waiting_for_body)
async def get_body(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_body", message.html_text, TemplateCreator.waiting_for_note,
                    "4️⃣ Введите <b>Заметку</b> (цитата):")


@router.message(TemplateCreator.waiting_for_note)
async def get_note(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_note", message.html_text, TemplateCreator.waiting_for_conclusion,
                    "5️⃣ Введите <b>Заключение</b>:")


@router.message(TemplateCreator.waiting_for_conclusion)
async def get_conclusion(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_conclusion", message.html_text, TemplateCreator.waiting_for_hashtags,
                    "6️⃣ Введите <b>Хештеги</b>:")


@router.message(TemplateCreator.waiting_for_hashtags)
async def get_hashtags(message: types.Message, state: FSMContext):
    await next_step(message, state, "t_hashtags", message.html_text, TemplateCreator.waiting_for_links,
                    "7️⃣ Введите <b>Ссылки</b>:")


@router.message(TemplateCreator.waiting_for_links)
async def get_links(message: types.Message, state: FSMContext):
    await finalize_template(message, state, is_skip=False)


# --- ФИНАЛИЗАЦИЯ И ВЫВОД ---
async def finalize_template(message: types.Message, state: FSMContext, is_skip=False):
    try:
        links = message.html_text if not is_skip else ""
        data = await state.get_data()

        res = []
        if data.get("t_title"): res.append(f"<b>{data['t_title']}</b>")
        if data.get("t_subtitle"): res.append(f"<i>{data['t_subtitle']}</i>")
        if data.get("t_body"): res.append(f"\n{data['t_body']}")
        if data.get("t_note"): res.append(f"\n<blockquote>{data['t_note']}</blockquote>")
        if data.get("t_conclusion"): res.append(f"\n{data['t_conclusion']}")
        if data.get("t_hashtags"): res.append(f"\n<i>{data['t_hashtags']}</i>")
        if links: res.append(f"\n{links}")

        final_text = "\n".join(res)

        has_prem = False
        if not is_skip and message.entities:
            for ent in message.entities:
                if ent.type == "custom_emoji": has_prem = True
        is_premium_used = data.get("has_premium", False) or has_prem

        # Предпросмотр (как будет в канале)
        await message.answer("👀 <b>Предпросмотр вашего поста:</b>")
        await message.answer(final_text, parse_mode="HTML", disable_web_page_preview=True)

        # Подготовка кода для копирования
        escaped_text = html.escape(final_text)
        warn = ""
        if is_premium_used:
            warn = ("\n\n⚠️ <b>ВНИМАНИЕ:</b> В тексте есть премиум-эмодзи. "
                    "Они отобразятся только в каналах с <b>Boost 2+ уровня</b>.")

        # Улучшенное сообщение с инструкцией
        await message.answer(
            f"✨ <b>Текст готов к копированию!</b>\n\n"
            f"📱 <b>Для телефона:</b> Нажмите на текст ниже (скопируется само).\n"
            f"💻 <b>Для ПК:</b> Выделите текст ниже и нажмите <code>Ctrl+C</code>.\n\n"
            f"<code>{escaped_text}</code>"
            f"{warn}",
            reply_markup=reply.main_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Ошибка сборки шаблона: {e}")
        await message.answer(f"❌ Ошибка при сборке: {e}", reply_markup=reply.main_menu())
    finally:
        await state.clear()