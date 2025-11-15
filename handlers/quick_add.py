import asyncio
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_database import User, Travel, Entry, Media
from app.travel_states import QuickAddState
from app.travel_utils import rate_limiter, validate_city, validate_place_title, validate_comment, validate_country, \
    validate_rating, progress_manager, geocoding
import app.traveler_keyboard as kb

router = Router()


@router.callback_query(F.data == "quick_add_place")
async def quick_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🚀 <b>Быстрое добавление места</b>\n\n"
        "Эта функция создаст однодневное путешествие и добавит в него место.\n\n"
        "🌍 <b>В какой стране вы находитесь?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_menu")]
        ])
    )
    await state.set_state(QuickAddState.country)

@router.message(QuickAddState.country)
async def quick_add_country(message: Message, state: FSMContext):
    if not validate_country(message.text):
        await message.answer("❌ Некорректное название страны. Используйте только буквы и дефисы.")
        return

    await state.update_data(country=message.text)
    await message.answer(
        "🏙️ <b>В каком городе вы находитесь?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuickAddState.city)


@router.message(QuickAddState.city)
async def quick_add_city(message: Message, state: FSMContext):
    if not validate_city(message.text):
        await message.answer("❌ Некорректное название города. Используйте только буквы и дефисы.")
        return

    await state.update_data(city=message.text)
    await message.answer(
        "📍 <b>Какое место вы хотите добавить?</b>\n"
        "(Например: Эйфелева башня, Центральный парк, Ресторан 'У озера')",
        parse_mode="HTML"
    )
    await state.set_state(QuickAddState.place_title)


@router.message(QuickAddState.place_title)
async def quick_add_place_title(message: Message, state: FSMContext):
    if not validate_place_title(message.text):
        await message.answer("❌ Слишком длинное название места (макс. 100 символов)")
        return

    await state.update_data(place_title=message.text)
    await message.answer(
        "💬 <b>Добавьте комментарий к месту</b>\n"
        "(Или отправьте \"-\" чтобы пропустить)",
        parse_mode="HTML"
    )
    await state.set_state(QuickAddState.place_comment)


@router.message(QuickAddState.place_comment)
async def quick_add_place_comment(message: Message, state: FSMContext):
    if not validate_comment(message.text):
        await message.answer("❌ Комментарий слишком длинный (макс. 500 символов)")
        return

    await state.update_data(place_comment=message.text)

    # Начинаем процесс определения координат
    data = await state.get_data()

    await progress_manager.start_progress(
        message.bot,
        message.from_user.id,
        "Определение координат",
        message
    )

    await progress_manager.update_progress(
        message.bot,
        message.from_user.id,
        "Определение координат",
        20,
        "Подготовка запроса"
    )

    await asyncio.sleep(0.5)

    await progress_manager.update_progress(
        message.bot,
        message.from_user.id,
        "Определение координат",
        40,
        "Поиск местоположения"
    )

    country = data['country']
    city = data['city']
    place_title = data['place_title']

    lat, lon = geocoding(country, city, place_title)

    if lat and lon:
        await progress_manager.update_progress(
            message.bot,
            message.from_user.id,
            "Определение координат",
            70,
            "Сохранение данных"
        )

        # Сохраняем координаты в состоянии
        await state.update_data(latitude=lat, longitude=lon)

        await progress_manager.update_progress(
            message.bot,
            message.from_user.id,
            "Определение координат",
            90,
            "Завершение операции"
        )

        await progress_manager.complete_progress(
            message.bot,
            message.from_user.id,
            "Определение координат",
            True,
            f"📍 Координаты определены: {lat:.5f}, {lon:.5f}"
        )

        await show_date_selection(message, state)

    else:
        await progress_manager.complete_progress(
            message.bot,
            message.from_user.id,
            "Определение координат",
            False
        )

        await message.answer(
            "❌ Не удалось автоматически определить координаты для:\n"
            f"<b>{place_title}</b> в <b>{city}</b>\n\n"
            "📍 <b>Вы можете:</b>\n"
            "• Отправить геолокацию через кнопку \"📎\" (в Attach)\n"
            "• Ввести координаты вручную\n"
            "• Продолжить без координат\n\n"
            "💡 <i>Координаты нужны для отображения на карте</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📍 Отправить геолокацию", callback_data="quick_location")],
                [InlineKeyboardButton(text="📝 Ввести координаты", callback_data="quick_coordinates_input")],
                [InlineKeyboardButton(text="⏭️ Продолжить без координат", callback_data="quick_skip_coordinates")]
            ])
        )


async def show_date_selection(message: Message, state: FSMContext):
    today = datetime.now().strftime("%d.%m.%Y")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")

    date_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 Сегодня ({today})", callback_data="quick_date:today")],
        [InlineKeyboardButton(text=f"📅 Вчера ({yesterday})", callback_data="quick_date:yesterday")],
        [InlineKeyboardButton(text="📅 Другая дата", callback_data="quick_date:custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_add_place")]
    ])

    await message.answer(
        "📅 <b>Когда вы посетили это место?</b>",
        parse_mode="HTML",
        reply_markup=date_keyboard
    )
    await state.set_state(QuickAddState.date)


@router.callback_query(F.data == "quick_location")
async def quick_location_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📍 Отправьте геолокацию места:\n\n"
        "Нажмите на кнопку \"📎\" (Attach) → Location → Отправьте ваше местоположение",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_back_to_coordinates")]
        ])
    )
    await state.set_state(QuickAddState.waiting_location)


@router.callback_query(F.data == "quick_coordinates_input")
async def quick_coordinates_input_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📝 <b>Ввод координат</b>\n\n"
        "Введите координаты в формате:\n"
        "• <code>59.93428, 30.33510</code>\n"
        "• <code>59.93428 30.33510</code>\n\n"
        "Первое число - широта, второе - долгота",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_back_to_coordinates")]
        ])
    )
    await state.set_state(QuickAddState.waiting_coordinates_input)


@router.callback_query(F.data == "quick_skip_coordinates")
async def quick_skip_coordinates_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(latitude=None, longitude=None)
    await callback.answer("✅ Координаты пропущены")
    await show_date_selection(callback.message, state)


@router.callback_query(F.data == "quick_back_to_coordinates")
async def quick_back_to_coordinates(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.answer(
        "❌ Не удалось автоматически определить координаты\n\n"
        "📍 <b>Вы можете:</b>\n"
        "• Отправить геолокацию\n"
        "• Ввести координаты вручную\n"
        "• Продолжить без координат",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 Отправить геолокацию", callback_data="quick_location")],
            [InlineKeyboardButton(text="📝 Ввести координаты", callback_data="quick_coordinates_input")],
            [InlineKeyboardButton(text="⏭️ Продолжить без координат", callback_data="quick_skip_coordinates")]
        ])
    )


@router.message(QuickAddState.waiting_location, F.content_type == "location")
async def handle_quick_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude

    await state.update_data(latitude=lat, longitude=lon)
    await message.answer(
        f"✅ Геолокация сохранена!\n"
        f"📍 Широта: {lat:.5f}\n"
        f"📍 Долгота: {lon:.5f}"
    )
    await show_date_selection(message, state)


@router.message(QuickAddState.waiting_coordinates_input)
async def handle_quick_coordinates_input(message: Message, state: FSMContext):
    try:
        coords_text = message.text.strip()

        if ',' in coords_text:
            lat_str, lon_str = coords_text.split(',', 1)
        elif ' ' in coords_text:
            parts = coords_text.split()
            if len(parts) >= 2:
                lat_str, lon_str = parts[0], parts[1]
            else:
                await message.answer("❌ Неверный формат. Нужно две координаты через пробел или запятую")
                return
        else:
            await message.answer("❌ Неверный формат координат")
            return

        lat = float(lat_str.strip())
        lon = float(lon_str.strip())

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            await message.answer("❌ Неверные координаты:\n• Широта от -90 до 90\n• Долгота от -180 до 180")
            return

        await state.update_data(latitude=lat, longitude=lon)
        await message.answer(
            f"✅ Координаты сохранены!\n"
            f"📍 Широта: {lat:.5f}\n"
            f"📍 Долгота: {lon:.5f}"
        )
        await show_date_selection(message, state)

    except ValueError:
        await message.answer("❌ Неверный числовой формат координат")
    except Exception as e:
        await message.answer("❌ Ошибка обработки координат")


@router.callback_query(F.data.startswith("quick_date:"), QuickAddState.date)
async def quick_add_date(callback: CallbackQuery, state: FSMContext):
    date_type = callback.data.split(":")[1]

    if date_type == "today":
        selected_date = datetime.now()
    elif date_type == "yesterday":
        selected_date = datetime.now() - timedelta(days=1)
    else:  # custom
        await callback.message.answer(
            "📅 <b>Введите дату посещения в формате ДД.ММ.ГГГГ</b>",
            parse_mode="HTML"
        )
        await state.set_state(QuickAddState.custom_date)
        return

    await process_quick_add_final(callback, state, selected_date)
    await callback.answer()


async def process_quick_add_final(callback: CallbackQuery, state: FSMContext, visit_date: datetime):
    data = await state.get_data()
    session = Session()

    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return

        # Создаем однодневное путешествие
        travel = Travel(
            user_id=user.user_id,
            country=data["country"],
            start_date=visit_date,
            end_date=visit_date + timedelta(days=1),  # +1 день для корректной длительности
            travel_comment="Создано через быстрое добавление"
        )
        session.add(travel)
        session.flush()

        # Создаем запись о месте с координатами
        entry = Entry(
            travel_id=travel.travel_id,
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=visit_date,
            latitude=data.get("latitude"),
            longitude=data.get("longitude")
        )
        session.add(entry)
        session.commit()

        # Сохраняем place_id в состоянии для добавления медиа
        await state.update_data(place_id=entry.place_id)

        # Обновляем статистику пользователя
        user.entries_count = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id
        ).count()

        session.commit()

        # Формируем сообщение об успехе
        success_text = "✅ <b>Место успешно добавлено!</b>\n\n"
        success_text += f"📍 <b>{data['place_title']}</b>\n"
        success_text += f"🏙️ {data['city']}, 🌍 {data['country']}\n"
        success_text += f"📅 {visit_date.strftime('%d.%m.%Y')}\n"

        if data.get("latitude") and data.get("longitude"):
            success_text += f"📍 Координаты: {data['latitude']:.5f}, {data['longitude']:.5f}\n\n"
            success_text += "🗺️ <i>Место будет отображаться на карте</i>\n\n"
        else:
            success_text += "\n⚠️ <i>Координаты не добавлены - место не будет отображаться на карте</i>\n\n"

        success_text += "Что дальше?"

        await callback.message.answer(
            success_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo_quick")],
                [InlineKeyboardButton(text="🎥 Добавить видео", callback_data="add_video_quick")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{entry.place_id}")],
                [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
            ])
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при добавлении места: {str(e)}")
        print(f"Ошибка быстрого добавления: {e}")
        session.rollback()
    finally:
        session.close()


async def process_quick_add_final_message(message: Message, state: FSMContext, visit_date: datetime):
    data = await state.get_data()
    session = Session()

    try:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Создаем однодневное путешествие
        travel = Travel(
            user_id=user.user_id,
            country=data["country"],
            start_date=visit_date,
            end_date=visit_date + timedelta(days=1),
            travel_comment="Создано через быстрое добавление"
        )
        session.add(travel)
        session.flush()

        # Создаем запись о месте с координатами
        entry = Entry(
            travel_id=travel.travel_id,
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=visit_date,
            latitude=data.get("latitude"),
            longitude=data.get("longitude")
        )
        session.add(entry)
        session.commit()

        # Сохраняем place_id в состоянии для добавления медиа
        await state.update_data(place_id=entry.place_id)

        # Обновляем статистику пользователя
        user.entries_count = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id
        ).count()

        session.commit()

        # Формируем сообщение об успехе
        success_text = "✅ <b>Место успешно добавлено!</b>\n\n"
        success_text += f"📍 <b>{data['place_title']}</b>\n"
        success_text += f"🏙️ {data['city']}, 🌍 {data['country']}\n"
        success_text += f"📅 {visit_date.strftime('%d.%m.%Y')}\n"

        if data.get("latitude") and data.get("longitude"):
            success_text += f"📍 Координаты: {data['latitude']:.5f}, {data['longitude']:.5f}\n\n"
            success_text += "🗺️ <i>Место будет отображаться на карте</i>\n\n"
        else:
            success_text += "\n⚠️ <i>Координаты не добавлены - место не будет отображаться на карте</i>\n\n"

        success_text += "Что дальше?"

        await message.answer(
            success_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo_quick")],
                [InlineKeyboardButton(text="🎥 Добавить видео", callback_data="add_video_quick")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{entry.place_id}")],
                [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
            ])
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении места: {str(e)}")
        print(f"Ошибка быстрого добавления: {e}")
        session.rollback()
    finally:
        session.close()
        await state.clear()


@router.callback_query(F.data == "add_photo_quick")
async def add_photo_quick(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📸 <b>Добавление фото</b>\n\n"
        "Отправьте фото для этого места:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_add_back")]
        ])
    )
    await state.set_state(QuickAddState.adding_photo)


@router.callback_query(F.data == "add_video_quick")
async def add_video_quick(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎥 <b>Добавление видео</b>\n\n"
        "Отправьте видео для этого места:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_add_back")]
        ])
    )
    await state.set_state(QuickAddState.adding_video)


@router.message(QuickAddState.adding_photo, F.photo)
async def handle_quick_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    place_id = data.get('place_id')

    if not place_id:
        await message.answer("❌ Ошибка: не найден идентификатор места")
        return

    session = Session()
    try:
        file_id = message.photo[-1].file_id
        media = Media(place_id=place_id, media_type='photo', file_id=file_id)
        session.add(media)
        session.commit()

        await message.answer(
            "✅ Фото добавлено!\n\n"
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить еще фото", callback_data="add_photo_quick")],
                [InlineKeyboardButton(text="🎥 Добавить видео", callback_data="add_video_quick")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{place_id}")],
                [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
            ])
        )

    except Exception as e:
        await message.answer("❌ Ошибка при добавлении фото")
        print(f"Ошибка добавления фото: {e}")
    finally:
        session.close()


@router.message(QuickAddState.adding_video, F.video)
async def handle_quick_video(message: Message, state: FSMContext):
    data = await state.get_data()
    place_id = data.get('place_id')

    if not place_id:
        await message.answer("❌ Ошибка: не найден идентификатор места")
        return

    session = Session()
    try:
        file_id = message.video.file_id
        media = Media(place_id=place_id, media_type='video', file_id=file_id)
        session.add(media)
        session.commit()

        await message.answer(
            "✅ Видео добавлено!\n\n"
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo_quick")],
                [InlineKeyboardButton(text="🎥 Добавить еще видео", callback_data="add_video_quick")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{place_id}")],
                [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
            ])
        )

    except Exception as e:
        await message.answer("❌ Ошибка при добавлении видео")
        print(f"Ошибка добавления видео: {e}")
    finally:
        session.close()


@router.callback_query(F.data == "quick_add_back")
async def quick_add_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    place_id = data.get('place_id')

    if place_id:
        await callback.message.answer(
            "↩️ <b>Возврат к управлению местом</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo_quick")],
                [InlineKeyboardButton(text="🎥 Добавить видео", callback_data="add_video_quick")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{place_id}")],
                [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
            ])
        )
    else:
        await callback.message.answer(
            "❌ Не удалось вернуться к управлению местом",
            reply_markup=kb.back_to_menu_keyboard
        )

@router.message(QuickAddState.custom_date)
async def quick_add_custom_date(message: Message, state: FSMContext):
    try:
        visit_date = datetime.strptime(message.text, "%d.%m.%Y")
        if visit_date > datetime.now():
            await message.answer("❌ Дата не может быть в будущем")
            return

        await process_quick_add_final_message(message, state, visit_date)

    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")


async def process_quick_add_final_message(message: Message, state: FSMContext, visit_date: datetime):
    data = await state.get_data()
    session = Session()

    try:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Создаем однодневное путешествие
        travel = Travel(
            user_id=user.user_id,
            country="Быстрое добавление",
            start_date=visit_date,
            end_date=visit_date,
            travel_comment="Создано через быстрое добавление"
        )
        session.add(travel)
        session.flush()

        # Создаем запись о месте
        entry = Entry(
            travel_id=travel.travel_id,
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=visit_date
        )
        session.add(entry)
        session.commit()

        # Обновляем статистику пользователя
        user.entries_count = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id
        ).count()

        session.commit()

        await message.answer(
            "✅ <b>Место успешно добавлено!</b>\n\n"
            f"📍 <b>{data['place_title']}</b>\n"
            f"🏙️ {data['city']}\n"
            f"📅 {visit_date.strftime('%d.%m.%Y')}\n\n"
            "Хотите добавить фото или оценить это место?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data=f"add_photo_to:{entry.place_id}")],
                [InlineKeyboardButton(text="⭐ Оценить место", callback_data=f"rate_place:{entry.place_id}")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
            ])
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении места: {str(e)}")
        print(f"Ошибка быстрого добавления: {e}")
        session.rollback()
    finally:
        session.close()
        await state.clear()


@router.callback_query(F.data.startswith("rate_place:"))
async def rate_place_quick(callback: CallbackQuery, state: FSMContext):
    try:
        place_id = int(callback.data.split(":")[1])
    except ValueError:
        await callback.answer("❌ Ошибка данных")
        return

    await state.update_data(place_id=place_id)
    await callback.message.answer(
        "⭐ <b>Оценка места</b>\n\n"
        "Как вы оцениваете это место? (от 1 до 10):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_add_back")]
        ])
    )
    await state.set_state(QuickAddState.rating)


@router.message(QuickAddState.rating)
async def handle_quick_rating(message: Message, state: FSMContext):
    if not validate_rating(message.text):
        await message.answer("❌ Оценка должна быть числом от 1 до 10")
        return

    data = await state.get_data()
    place_id = data.get('place_id')

    if not place_id:
        await message.answer("❌ Ошибка: не найден идентификатор места")
        return

    session = Session()
    try:
        entry = session.query(Entry).filter_by(place_id=place_id).first()
        if entry:
            entry.place_rating = int(message.text)
            session.commit()

            await message.answer(
                f"✅ Место оценено на {message.text}⭐!\n\n"
                "Что дальше?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo_quick")],
                    [InlineKeyboardButton(text="🎥 Добавить видео", callback_data="add_video_quick")],
                    [InlineKeyboardButton(text="🏠 Завершить", callback_data="back_to_menu")]
                ])
            )
        else:
            await message.answer("❌ Место не найдено")

    except Exception as e:
        await message.answer("❌ Ошибка при оценке места")
        print(f"Ошибка оценки: {e}")
    finally:
        session.close()
    await state.clear()