from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_states import EntryState
from app.travel_database import Media, MediaTypeEnum
from app.travel_utils import can_add_media, rate_limiter
import app.traveler_keyboard as kb

router = Router()

@router.message(EntryState.place_media)
async def place_media_input(msg: Message):
    await msg.answer('📸 Хотите добавить фото или видео этого места?', reply_markup=kb.type_media_keyboard)

@router.callback_query(F.data == 'photo')
async def add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('📸 Отправьте фото:')
    await state.set_state(EntryState.adding_more_photo)

@router.callback_query(F.data == 'video')
async def add_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('🎥 Отправьте видео:')
    await state.set_state(EntryState.adding_more_video)

@router.message(EntryState.adding_more_photo)
async def adding_more_photo_input(msg: Message, state: FSMContext):
    if not rate_limiter.is_allowed(msg.from_user.id, "media_upload"):
        await msg.answer("❌ Слишком много загрузок. Подождите 2 минуты.")
        return

    data = await state.get_data()
    place_id = data.get('place_id')
    session = Session()
    try:
        file_id = msg.photo[-1].file_id
        media = Media(place_id=place_id, media_type=MediaTypeEnum.photo, file_id=file_id)
        session.add(media)
        session.commit()
        await msg.answer('✅ Фото добавлено.')
    finally:
        session.close()
    if not can_add_media(tg_id=msg.from_user.id, place_id=place_id):
        await msg.answer('⚠️ Вы достигли лимита добавления медиа')
        await msg.answer('⭐ Как вы оцениваете это место? (от 1 до 10)')
        await state.set_state(EntryState.place_rating)
    else:
        await msg.answer('➕ Добавить еще медиа?', reply_markup=kb.media_more_keyboard)

@router.message(EntryState.adding_more_video)
async def adding_more_video_input(msg: Message, state: FSMContext):
    if not rate_limiter.is_allowed(msg.from_user.id, "media_upload"):
        await msg.answer("❌ Слишком много загрузок. Подождите 2 минуты.")
        return

    data = await state.get_data()
    place_id = data.get('place_id')
    session = Session()
    try:
        file_id = msg.video.file_id
        media = Media(place_id=place_id, media_type=MediaTypeEnum.video, file_id=file_id)
        session.add(media)
        session.commit()
        await msg.answer('✅ Видео добавлено.')
    finally:
        session.close()
    if not can_add_media(tg_id=msg.from_user.id, place_id=place_id):
        await msg.answer('⚠️ Вы достигли лимита добавления медиа')
        await msg.answer('⭐ Как вы оцениваете это место? (от 1 до 10)')
        await state.set_state(EntryState.place_rating)
    else:
        await msg.answer('➕ Добавить еще медиа?', reply_markup=kb.media_more_keyboard)

@router.callback_query(F.data == 'add_photo_again')
async def add_photo_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('📸 Отправьте следующее фото:')
    await state.set_state(EntryState.adding_more_photo)

@router.callback_query(F.data == 'add_video_again')
async def add_video_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('🎥 Отправьте следующее видео:')
    await state.set_state(EntryState.adding_more_video)

@router.callback_query(F.data == 'finish_media')
async def finish_media(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('➡️ Продолжаем...')
    await callback.message.answer('⭐ Как вы оцениваете это место? (от 1 до 10)')
    await state.set_state(EntryState.place_rating)