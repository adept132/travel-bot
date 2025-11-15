from venv import logger

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_states import Menu, TravelState, EntryState
from app.travel_database import User, Travel
import app.traveler_keyboard as kb

router = Router()

@router.message(Menu.menu)
async def menu_input(msg: Message):
    await msg.answer(f'👋 Привет, {msg.from_user.first_name}!\n❓ Что вы хотите сделать?', reply_markup=kb.menu_keyboard)

@router.callback_query(F.data == "start_travel")
async def start_travel_from_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('🌍 Давайте начнем новое путешествие!\nКакую страну вы посещаете?')
    await state.set_state(TravelState.country)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Menu.menu)
    await callback.message.answer(
        f'👋 Привет, {callback.from_user.first_name}!\n❓ Что бы ты хотел сделать?',
        reply_markup=kb.menu_keyboard
    )

@router.callback_query(F.data == "profile_check")
async def profile_check(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
    finally:
        session.close()
    text = (
        "🗺️ *ПРОФИЛЬ ПУТЕШЕСТВЕННИКА*\n\n"
        f"👤 *Имя:* {user.name}\n"
        f"✈️ *Путешествий:* {user.trip_count or 0}\n"
        f"🏛️ *Посещенных мест:* {user.entries_count or 0}\n"
        f"📷 *Фотографий:* {user.photos_count or 0}\n"
        f"🕐 *Рекорд путешествия:* {user.longest_trip or 0} дней\n"
    )
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb.back_to_menu_keyboard)

@router.callback_query(F.data == 'continue_travel')
async def choose_existing_travel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    session = Session()
    user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
    if not user:
        await callback.message.edit_text("⛔ Нет такого пользователя", reply_markup=kb.menu_keyboard)
        session.close()
        return

    travels = session.query(Travel).filter_by(user_id=user.user_id).all()
    session.close()

    if not travels:
        return await callback.message.edit_text(
            "⛔ У тебя нету активных путешествий",
            reply_markup=kb.menu_keyboard
        )

    travel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'🌍 {t.country}', callback_data=f"select_travel:{t.travel_id}")]
        for t in travels
    ])
    travel_kb.inline_keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    )

    await callback.message.edit_text('🎒 Выбрать путешествие', reply_markup=travel_kb)

def get_travel(travel_id: int, user_tg_id: int):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=user_tg_id).first()
        if not user:
            return None

        travel = session.query(Travel).filter_by(
            travel_id=travel_id,
            user_id=user.user_id
        ).first()
        return travel
    except Exception as e:
        logger.error(f"Security error in get_travel: {e}")
        return None
    finally:
        session.close()

@router.callback_query(F.data.startswith("select_travel:"))
async def process_selected_travel(callback: CallbackQuery, state: FSMContext):
    try:
        travel_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный формат данных")
        return

    if travel_id <= 0:
        await callback.answer("❌ Неверный идентификатор")
        return

    travel = get_travel(travel_id, callback.from_user.id)
    if not travel:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    session = Session()
    travel = session.query(Travel).filter_by(travel_id=travel_id).first()
    session.close()

    if not travel:
        return await callback.answer('❌ Путешествие не найдено', show_alert=True)

    await state.update_data(travel_id=travel_id)

    await callback.message.edit_text(
        f'📍 Добавляем место в путешествие:\n<b>🌍 {travel.country}</b>\n\n🏙️ В каком городе вы находитесь?',
        parse_mode="HTML"
    )

    await state.set_state(EntryState.city)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Menu:", reply_markup=kb.menu_keyboard)