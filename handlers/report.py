from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from app.travel_session import Session
from app.travel_database import User, Travel, Entry, Media
import app.traveler_keyboard as kb

router = Router()

@router.callback_query(F.data == "report")
async def choose_travel_for_report(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        travels = session.query(Travel).filter_by(user_id=user.user_id).order_by(Travel.start_date.desc()).all()

        if not travels:
            await callback.message.answer("🚫 У вас нет путешествий для отчета")
            return

        keyboard = []
        for travel in travels:
            days = (travel.end_date - travel.start_date).days if travel.start_date and travel.end_date else 0
            button_text = f"🌍 {travel.country} ({days} дней)"
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"report_travel:{travel.travel_id}")])

        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])

        await callback.message.answer(
            "📊 Выберите путешествие для отчета:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Ошибка")
        print(f"Ошибка выбора путешествия: {e}")
    finally:
        session.close()


@router.callback_query(F.data.startswith("report_travel:"))
async def send_travel_report(callback: CallbackQuery):
    session = Session()
    try:
        travel_id = int(callback.data.split(":")[1])
        travel = session.query(Travel).filter_by(travel_id=travel_id).first()

        if not travel:
            await callback.answer("❌ Путешествие не найдено")
            return

        user = session.query(User).filter_by(user_id=travel.user_id).first()
        days = (travel.end_date - travel.start_date).days if travel.start_date and travel.end_date else 0

        travel_text = (
            f"🏁 Отчет о путешествии:\n"
            f"🌍 Страна: {travel.country}\n"
            f"📅 Длительность: {days} дней\n"
            f"💬 Комментарий: {travel.travel_comment or 'Нет комментария'}\n"
            f"⭐ Оценка: {travel.travel_rating or 'Не оценено'}"
        )

        await callback.message.answer(travel_text)

        entries = session.query(Entry).filter_by(travel_id=travel.travel_id).all()

        if not entries:
            await callback.message.answer("📍 В этом путешествии нет посещенных мест")
        else:
            for entry in entries:
                place_text = (
                    f"📍 {entry.city} - {entry.place_title}\n"
                    f"💬 {entry.place_comment or 'Нет комментария'}\n"
                    f"⭐ Оценка: {entry.place_rating or 'Не оценено'}"
                )

                photos = session.query(Media).filter_by(
                    place_id=entry.place_id,
                    media_type='photo'
                ).all()

                if photos:
                    media_group = []

                    media_group.append(
                        InputMediaPhoto(
                            media=photos[0].file_id,
                            caption=place_text
                        )
                    )
                    for photo in photos[1:10]:
                        media_group.append(
                            InputMediaPhoto(media=photo.file_id)
                        )

                    try:
                        await callback.message.answer_media_group(media_group)
                    except Exception as media_error:
                        print(f"Ошибка отправки медиагруппы: {media_error}")
                        await callback.message.answer(place_text)
                        for photo in photos[:5]:
                            try:
                                await callback.message.answer_photo(photo.file_id)
                            except Exception:
                                continue
                else:
                    await callback.message.answer(place_text)
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Выбрать другое путешествие", callback_data="report")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
        ])

        await callback.message.answer(
            "✅ Отчет завершен",
            reply_markup=back_keyboard
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("❌ Ошибка формирования отчета")
        print(f"Ошибка в отчете: {e}")
    finally:
        session.close()