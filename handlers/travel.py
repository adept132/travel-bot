from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_states import TravelState, TravelFinish, EntryState, Menu
from app.travel_database import Travel, User, MediaTypeEnum, Entry, Media
import app.traveler_keyboard as kb
from app.travel_utils import validate_country, validate_date, check_achievements, validate_rating, date_difference

router = Router()


@router.callback_query(F.data == 'start_travel')
async def start_travel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer('🌍 Какую страну вы посещаете?')
    await state.set_state(TravelState.country)
    await callback.answer()

@router.message(TravelState.country)
async def country_input(msg: Message, state: FSMContext):
    if not validate_country(msg.text):
        await msg.answer("❌ Некорректное название страны. Используйте только буквы и дефисы.")
        return

    await state.update_data(country=msg.text)
    await msg.answer('📅 Когда началось ваше путешествие?')
    await state.set_state(TravelState.start_date)

@router.message(TravelState.start_date)
async def start_date_input(msg: Message, state: FSMContext):
    if not validate_date(msg.text):
        await msg.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return

    await state.update_data(start_date=msg.text)
    await msg.answer('📅 Когда заканчивается ваше путешествие?')
    await state.set_state(TravelState.end_date)

@router.message(TravelState.end_date)
async def end_date_input(msg: Message, state: FSMContext):
    if not validate_date(msg.text):
        await msg.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return

    data = await state.get_data()
    session = Session()

    start_date = datetime.strptime(data["start_date"], "%d.%m.%Y")
    end_date = datetime.strptime(msg.text, "%d.%m.%Y")

    if end_date <= start_date:
        await msg.answer("❌ Дата окончания должна быть позже даты начала")
        return

    try:
        user = session.query(User).filter_by(tg_id=msg.from_user.id).first()
        if not user:
            user = User(
                tg_id=msg.from_user.id,
                name=msg.from_user.first_name
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        travel = Travel(
            user_id=user.user_id,
            country=data["country"],
            start_date=datetime.strptime(data["start_date"], "%d.%m.%Y"),
            end_date=datetime.strptime(msg.text, "%d.%m.%Y")
        )
        session.add(travel)
        session.commit()
        await state.update_data(travel_id=travel.travel_id)
    finally:
        session.close()
    await msg.answer('✅ Путешествие создано!\n\nТеперь добавьте первое место!\n🏙️ Какой город вы посещаете?')
    await state.set_state(EntryState.city)

@router.callback_query(F.data == "finish_travel")
async def finish_travel(callback, state: FSMContext):
    await callback.answer()
    await callback.message.answer('⭐ Оцените ваше путешествие от 1 до 10:')
    await state.set_state(TravelFinish.travel_rating)

@router.message(TravelFinish.travel_rating)
async def travel_rating_input(msg: Message, state: FSMContext):
    if not validate_rating(msg.text):
        await msg.answer("❌ Оценка должна быть числом от 1 до 10")
        return

    await state.update_data(travel_rating=int(msg.text))
    await msg.answer('💬 Добавьте комментарий к путешествию (или "-" чтобы пропустить):')
    await state.set_state(TravelFinish.travel_comment)


@router.message(TravelFinish.travel_comment)
async def travel_comment_input(msg: Message, state: FSMContext):
    try:
        data = await state.get_data()
        session = Session()
        try:
            travel = session.query(Travel).filter_by(travel_id=data['travel_id']).first()
            if travel:
                travel.travel_rating = data['travel_rating']
                travel.travel_comment = None if msg.text == '-' else msg.text

            user = session.query(User).filter_by(tg_id=msg.from_user.id).first()
            if user:
                user.trip_count = session.query(Travel).filter_by(user_id=user.user_id).count()

                user.entries_count = session.query(Entry).join(Travel).filter(
                    Travel.user_id == user.user_id
                ).count()

                user.photos_count = session.query(Media).join(Entry).join(Travel).filter(
                    Travel.user_id == user.user_id,
                    Media.media_type == MediaTypeEnum.photo
                ).count()
                travels = session.query(Travel).filter_by(user_id=user.user_id).all()
                max_duration = 0
                for t in travels:
                    if t.start_date and t.end_date:
                        duration = date_difference(t.start_date, t.end_date)
                        if duration > max_duration:
                            max_duration = duration

                user.longest_trip = max_duration

            session.commit()
            if user:
                new_achievements = check_achievements(user, session)
                session.commit()
                if new_achievements:
                    for ach in new_achievements:
                        await msg.answer(
                            f'🏆 <b>Новое достижение!</b>\n\n<b>{ach.achievement_name}</b>\n{ach.description}',
                            parse_mode='HTML'
                        )
        except Exception as e:
            print(f"❌ Ошибка в travel_comment_input: {e}")
            session.rollback()
            await msg.answer("❌ Ошибка при сохранении путешествия")
            return
        finally:
            session.close()

        await msg.answer('Ваше путешествие сохранено!\nСпасибо за использование Travel Bot! 🎉')
        await msg.answer('❓ Что вы хотите сделать дальше?', reply_markup=kb.menu_keyboard)
        await state.set_state(Menu.menu)

    except Exception as e:
        print(f"❌ Критическая ошибка в travel_comment_input: {e}")
        await msg.answer("❌ Произошла критическая ошибка")
