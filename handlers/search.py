from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import func

from app.travel_session import Session
from app.travel_database import User, Travel, Entry
from app.travel_utils import rate_limiter
import app.traveler_keyboard as kb

router = Router()


@router.callback_query(F.data == "smart_search")
async def smart_search_menu(callback: CallbackQuery):
    search_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск мест", callback_data="search_places")],
        [InlineKeyboardButton(text="🌍 Поиск по странам", callback_data="search_countries")],
        [InlineKeyboardButton(text="⭐ Лучшие места", callback_data="search_top_rated")],
        [InlineKeyboardButton(text="📅 По датам", callback_data="search_by_date")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(
        "🔍 <b>Умный поиск</b>\n\n"
        "Найдите ваши места и путешествия по различным критериям:",
        parse_mode="HTML",
        reply_markup=search_keyboard
    )


@router.callback_query(F.data == "search_countries")
async def search_countries(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Получаем список стран пользователя
        countries = session.query(
            Travel.country,
            func.count(Travel.travel_id).label('travel_count'),
            func.count(Entry.place_id).label('places_count')
        ).join(Entry, Travel.travel_id == Entry.travel_id, isouter=True).filter(
            Travel.user_id == user.user_id
        ).group_by(Travel.country).order_by(Travel.country).all()

        if not countries:
            await callback.message.edit_text(
                "🌍 <b>Поиск по странам</b>\n\n"
                "У вас пока нет путешествий в разных странах.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="smart_search")]
                ])
            )
            return

        text = "🌍 <b>Ваши страны</b>\n\n"

        # Создаем клавиатуру с странами
        keyboard_buttons = []
        for country in countries:
            button_text = f"🌍 {country.country} ({country.travel_count} путешествий, {country.places_count} мест)"
            callback_data = f"search_country:{country.country.replace(' ', '_')}"
            keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="smart_search")])

        await callback.message.edit_text(
            "🌍 <b>Выберите страну для просмотра мест:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )

    except Exception as e:
        await callback.answer("❌ Ошибка загрузки стран")
        print(f"Ошибка поиска по странам: {e}")
    finally:
        session.close()


@router.callback_query(F.data.startswith("search_country:"))
async def search_country_places(callback: CallbackQuery):
    try:
        country = callback.data.split(":")[1].replace('_', ' ')
    except ValueError:
        await callback.answer("❌ Ошибка данных")
        return

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Получаем места в выбранной стране
        places = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id,
            Travel.country == country
        ).order_by(Entry.date.desc()).all()

        text = f"🌍 <b>Места в {country}</b>\n\n"

        for i, place in enumerate(places, 1):
            rating_text = f" ⭐ {place.place_rating}" if place.place_rating else ""
            text += f"{i}. <b>{place.place_title}</b>\n"
            text += f"   🏙️ {place.city}{rating_text}\n"
            text += f"   📅 {place.date.strftime('%d.%m.%Y')}\n\n"

        text += f"<i>Всего мест: {len(places)}</i>"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К списку стран", callback_data="search_countries")]
            ])
        )

    except Exception as e:
        await callback.answer("❌ Ошибка загрузки мест")
        print(f"Ошибка поиска по стране: {e}")
    finally:
        session.close()


@router.callback_query(F.data == "search_by_date")
async def search_by_date_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За последнюю неделю", callback_data="search_date:week")],
        [InlineKeyboardButton(text="📅 За последний месяц", callback_data="search_date:month")],
        [InlineKeyboardButton(text="📅 За последний год", callback_data="search_date:year")],
        [InlineKeyboardButton(text="📅 За все время", callback_data="search_date:all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="smart_search")]
    ])

    await callback.message.edit_text(
        "📅 <b>Поиск по датам</b>\n\n"
        "Выберите период для поиска мест:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("search_date:"))
async def search_by_date_execute(callback: CallbackQuery):
    period = callback.data.split(":")[1]

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Определяем дату начала в зависимости от периода
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(days=7)
            period_text = "последнюю неделю"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_text = "последний месяц"
        elif period == "year":
            start_date = now - timedelta(days=365)
            period_text = "последний год"
        else:  # all
            start_date = datetime(2000, 1, 1)  # очень старая дата
            period_text = "все время"

        # Ищем места за период
        if period == "all":
            places = session.query(Entry).join(Travel).filter(
                Travel.user_id == user.user_id
            ).order_by(Entry.date.desc()).all()
        else:
            places = session.query(Entry).join(Travel).filter(
                Travel.user_id == user.user_id,
                Entry.date >= start_date
            ).order_by(Entry.date.desc()).all()

        text = f"📅 <b>Места за {period_text}</b>\n\n"

        for i, place in enumerate(places[:20], 1):  # Ограничиваем 20 местами
            travel = session.query(Travel).filter_by(travel_id=place.travel_id).first()
            rating_text = f" ⭐ {place.place_rating}" if place.place_rating else ""
            text += f"{i}. <b>{place.place_title}</b>\n"
            text += f"   🏙️ {place.city}, 🌍 {travel.country if travel else 'N/A'}{rating_text}\n"
            text += f"   📅 {place.date.strftime('%d.%m.%Y')}\n\n"

        if not places:
            text += "📍 Мест не найдено"

        text += f"<i>Найдено мест: {len(places)}</i>"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К выбору периода", callback_data="search_by_date")]
            ])
        )

    except Exception as e:
        await callback.answer("❌ Ошибка поиска")
        print(f"Ошибка поиска по дате: {e}")
    finally:
        session.close()

@router.callback_query(F.data == "search_places")
async def search_places_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Поиск мест</b>\n\n"
        "Введите название места, города или ключевое слово для поиска:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="smart_search")]
        ])
    )
    await state.set_state("waiting_place_search")


@router.message(F.text, F.state == "waiting_place_search")
async def search_places_execute(message: Message, state: FSMContext):
    if not rate_limiter.is_allowed(message.from_user.id, "search"):
        await message.answer("❌ Слишком много запросов. Подождите немного.")
        return

    search_query = message.text.strip()
    if len(search_query) < 2:
        await message.answer("❌ Слишком короткий запрос. Введите минимум 2 символа.")
        return

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Ищем по названию места, городу и комментарию
        results = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id
        ).filter(
            (Entry.place_title.ilike(f"%{search_query}%")) |
            (Entry.city.ilike(f"%{search_query}%")) |
            (Entry.place_comment.ilike(f"%{search_query}%"))
        ).order_by(Entry.date.desc()).limit(20).all()

        if not results:
            await message.answer(
                f"🔍 По запросу \"{search_query}\" ничего не найдено.\n\n"
                "Попробуйте:\n"
                "• Другие ключевые слова\n"
                "• Название города\n"
                "• Часть названия места",
                reply_markup=kb.back_to_menu_keyboard
            )
            return

        text = f"🔍 <b>Результаты поиска: \"{search_query}\"</b>\n\n"

        for i, entry in enumerate(results, 1):
            travel = session.query(Travel).filter_by(travel_id=entry.travel_id).first()
            rating_text = f" ⭐ {entry.place_rating}" if entry.place_rating else ""
            text += f"{i}. <b>{entry.place_title}</b>\n"
            text += f"   🏙️ {entry.city}, 🌍 {travel.country if travel else 'N/A'}{rating_text}\n"
            text += f"   📅 {entry.date.strftime('%d.%m.%Y')}\n\n"

        text += f"<i>Найдено мест: {len(results)}</i>"

        await message.answer(text, parse_mode="HTML", reply_markup=kb.back_to_menu_keyboard)

    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {str(e)}")
        print(f"Ошибка поиска: {e}")
    finally:
        session.close()
    await state.clear()


@router.callback_query(F.data == "search_top_rated")
async def search_top_rated(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Топ-10 мест по рейтингу
        top_places = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id,
            Entry.place_rating.isnot(None)
        ).order_by(Entry.place_rating.desc()).limit(10).all()

        if not top_places:
            await callback.message.answer(
                "⭐ <b>Лучшие места</b>\n\n"
                "У вас пока нет оцененных мест.\n"
                "Добавьте оценки к вашим местам чтобы видеть их здесь!",
                parse_mode="HTML",
                reply_markup=kb.back_to_menu_keyboard
            )
            return

        text = "⭐ <b>Ваши лучшие места</b>\n\n"

        for i, place in enumerate(top_places, 1):
            travel = session.query(Travel).filter_by(travel_id=place.travel_id).first()
            text += f"{i}. <b>{place.place_title}</b> ⭐ {place.place_rating}\n"
            text += f"   🏙️ {place.city}, 🌍 {travel.country if travel else 'N/A'}\n"
            text += f"   📅 {place.date.strftime('%d.%m.%Y')}\n\n"

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_menu_keyboard)

    except Exception as e:
        await callback.answer("❌ Ошибка загрузки")
        print(f"Ошибка поиска топовых мест: {e}")
    finally:
        session.close()