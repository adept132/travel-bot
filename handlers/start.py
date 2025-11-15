from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.travel_session import Session
from app.travel_database import User
import app.traveler_keyboard as kb
from app.travel_states import Menu
from app.travel_utils import rate_limiter

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not rate_limiter.is_allowed(message.from_user.id):
        await message.answer("❌ Слишком много запросов. Подождите немного.")
        return

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if user is not None:
            await state.set_state(Menu.menu)
            await message.answer(
                f'👋 С возвращением, {message.from_user.first_name}!\n'
                f'Выберите действие в меню:',
                reply_markup=kb.menu_keyboard  # Клавиатура с основными опциями
            )
        else:
            await message.answer(
                f'👋 Привет, {message.from_user.first_name}!\n'
                f'Добро пожаловать в Travel Bot - ваш личный дневник путешествий!\n\n',
                reply_markup=kb.start_keyboard
                )
    finally:
        session.close()

@router.callback_query(F.data == 'info')
async def info_msg(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.answer('📖 Этот бот - ваш личный дневник путешествий.'
                                  '\n\nЗдесь вы можете сохранять воспоминания о местах, которые посещаете, оценивать их и добавлять фотографии ваших приключений!'
                                  , reply_markup=kb.after_info_keyboard)

@router.callback_query(F.data == 'start')
async def start_msg(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.answer('🎉 Отлично! Давайте начнем.\nНажмите кнопку ниже, чтобы создать первое путешествие.'
                                  , reply_markup=kb.travel_keyboard)
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id = callback.from_user.id).first()
        if not user:
            user = User(
                tg_id = callback.from_user.id, name = callback.from_user.first_name
            )
            session.add(user)
            session.commit()
            await callback.answer('Вы вошли')
    finally:
        session.close()