import asyncio
from datetime import datetime

from aiogram import F, Router
from aiogram.dispatcher.middlewares import data
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_states import EntryState
from app.travel_database import Entry, Travel, User
from app.travel_utils import (
    validate_city,
    validate_place_title,
    validate_comment,
    validate_rating,
    geocoding,
    save_place_with_coordinates, progress_manager, check_achievements, validate_date_within_travel, validate_date
)
import app.traveler_keyboard as kb

router = Router()


async def save_place_with_coordinates_local(msg: Message, state: FSMContext, lat: float, lon: float):
    data = await state.get_data()
    session = Session()
    try:
        visit_date = datetime.strptime(data["visitation_date"], "%d.%m.%Y")
        travel = session.query(Travel).filter_by(travel_id=data["travel_id"]).first()

        if travel and not validate_date_within_travel(visit_date, travel.start_date, travel.end_date):
            await msg.answer(
                f"❌ Ошибка: дата посещения выходит за пределы путешествия\n"
                f"📅 Путешествие: {travel.start_date.strftime('%d.%m.%Y')} - {travel.end_date.strftime('%d.%m.%Y')}\n"
                f"📅 Ваша дата: {visit_date.strftime('%d.%m.%Y')}"
            )
            return False

        entry = Entry(
            travel_id=data["travel_id"],
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=visit_date,
            latitude=lat,
            longitude=lon
        )

        user = session.query(User).filter_by(tg_id=msg.from_user.id).first()
        session.add(entry)
        session.commit()
        await state.update_data(place_id=entry.place_id)

        new_achievements = check_achievements(user, session)
        session.commit()

        for ach in new_achievements:
            await msg.answer(
                f'🏆 <b>Новое достижение!</b>\n\n<b>{ach.achievement_name}</b>\n{ach.description}',
                parse_mode='HTML'
            )

        return True

    except Exception as e:
        print(f"❌ Ошибка сохранения места: {e}")
        await msg.answer("❌ Ошибка при сохранении места")
        return False
    finally:
        session.close()

@router.message(EntryState.city)
async def city_input(msg: Message, state: FSMContext):
    if not validate_city(msg.text):
        await msg.answer("❌ Некорректное название города. Используйте только буквы, пробелы и дефисы.")
        return

    await state.update_data(city=msg.text)
    await msg.answer('📅 Когда вы посещаете этот город?')
    await state.set_state(EntryState.visitation_date)

@router.message(EntryState.visitation_date)
async def visitation_date_input(msg: Message, state: FSMContext):
    if not validate_date(msg.text):
        await msg.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return

    visit_date = datetime.strptime(msg.text, "%d.%m.%Y")

    data = await state.get_data()
    session = Session()
    try:
        travel = session.query(Travel).filter_by(travel_id=data["travel_id"]).first()
        if not travel:
            await msg.answer("❌ Ошибка: путешествие не найдено")
            return

        if not validate_date_within_travel(visit_date, travel.start_date, travel.end_date):
            await msg.answer(
                f"❌ Дата посещения должна быть в пределах путешествия:\n"
                f"📅 Начало: {travel.start_date.strftime('%d.%m.%Y')}\n"
                f"📅 Окончание: {travel.end_date.strftime('%d.%m.%Y')}\n\n"
                f"Введите дату в этом диапазоне:"
            )
            return

        await state.update_data(visitation_date=msg.text)
        await msg.answer('📍 О каком месте вы бы хотели создать запись? (Вы можете добавить только одно место за раз)')
        await state.set_state(EntryState.place_title)

    except Exception as e:
        await msg.answer("❌ Ошибка при проверке даты")
        print(f"Ошибка проверки даты: {e}")
    finally:
        session.close()

@router.message(EntryState.place_title)
async def place_title_input(msg: Message, state: FSMContext):
    if not validate_comment(msg.text):
        await msg.answer("❌ Комментарий слишком длинный (макс. 500 символов)")
        return

    await state.update_data(place_title=msg.text)
    await msg.answer('💬 Как бы вы прокомментировали это место?')
    await state.set_state(EntryState.place_comment)


@router.message(EntryState.place_comment)
async def place_comment_input(msg: Message, state: FSMContext):
    await state.update_data(place_comment=msg.text)
    data = await state.get_data()

    session = Session()
    try:
        travel = session.query(Travel).filter_by(travel_id=data["travel_id"]).first()
        country = travel.country if travel else None
    except:
        country = None
    finally:
        session.close()

    city = data['city']
    place_title = data['place_title']

    # СОЗДАЕМ ПРОГРЕСС-БАР ВРУЧНУЮ
    progress_msg = await msg.answer("⏳ <b>Определение координат</b>\n\n░░░░░░░░░░ 0%\n\n<i>Подготовка запроса...</i>",
                                    parse_mode="HTML")

    try:
        # Шаг 1: Подготовка запроса
        await progress_msg.edit_text(
            "⏳ <b>Определение координат</b>\n\n"
            "██░░░░░░░░ 20%\n\n"
            "<i>Подготовка запроса...</i>",
            parse_mode="HTML"
        )

        await asyncio.sleep(0.5)

        # Шаг 2: Поиск местоположения
        await progress_msg.edit_text(
            "⏳ <b>Определение координат</b>\n\n"
            "████░░░░░░ 40%\n\n"
            "<i>Поиск местоположения...</i>",
            parse_mode="HTML"
        )

        lat, lon = geocoding(country, city, place_title)

        if not lat or not lon:
            # ПРОГРЕСС ПРИ ОШИБКЕ
            await progress_msg.edit_text(
                "❌ <b>Определение координат прервано</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Не удалось определить координаты</i>",
                parse_mode="HTML"
            )

            # Отправляем сообщение об ошибке как новое сообщение
            await msg.answer(
                "❌ Не удалось автоматически определить координаты для:\n"
                f"<b>{place_title}</b> в <b>{city}</b>\n\n"
                "📍 <b>Вы можете:</b>\n"
                "• Отправить геолокацию через кнопку \"📎\" (в Attach)\n"
                "• Ввести координаты вручную в формате:\n"
                "  <code>12.34567, 89.01234</code>\n"
                "  <code>12.34567 89.01234</code>\n\n"
                "💡 <i>Или просто пропустите координаты и добавьте описание места</i>",
                parse_mode='HTML',
                reply_markup=kb.location_manual_keyboard
            )
            return await state.set_state(EntryState.location_manual)

        # Шаг 3: Сохранение данных
        await progress_msg.edit_text(
            "⏳ <b>Определение координат</b>\n\n"
            "███████░░░ 70%\n\n"
            "<i>Сохранение данных...</i>",
            parse_mode="HTML"
        )

        # Используем локальную функцию сохранения
        success = await save_place_with_coordinates_local(msg, state, lat, lon)

        if success:
            # Шаг 4: Завершение операции
            await progress_msg.edit_text(
                "⏳ <b>Определение координат</b>\n\n"
                "█████████░ 90%\n\n"
                "<i>Завершение операции...</i>",
                parse_mode="HTML"
            )

            await asyncio.sleep(0.5)

            # ФИНАЛЬНОЕ СООБЩЕНИЕ ОБ УСПЕХЕ
            await progress_msg.edit_text(
                f"✅ <b>Определение координат завершено!</b>\n\n"
                f"██████████ 100%\n\n"
                f"📍 Координаты сохранены: {lat:.5f}, {lon:.5f}\n\n"
                f"<i>Операция успешно выполнена</i> 🎉",
                parse_mode="HTML"
            )

            await msg.answer("📸 Хотите добавить фото или видео?", reply_markup=kb.type_media_keyboard)
            await state.set_state(EntryState.place_media)
        else:
            await progress_msg.edit_text(
                "❌ <b>Определение координат прервано</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Ошибка при сохранении данных</i>",
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"❌ Ошибка в процессе определения координат: {e}")
        try:
            await progress_msg.edit_text(
                "❌ <b>Определение координат прервано</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Произошла ошибка при выполнении</i>",
                parse_mode="HTML"
            )
        except:
            pass
        await msg.answer("❌ Произошла ошибка при определении координат")


@router.message(EntryState.location_manual, F.content_type == "location")
async def place_location_manual(msg: Message, state: FSMContext):
    data = await state.get_data()
    session = Session()
    try:
        visit_date = datetime.strptime(data["visitation_date"], "%d.%m.%Y")
        travel = session.query(Travel).filter_by(travel_id=data["travel_id"]).first()

        if travel and not validate_date_within_travel(visit_date, travel.start_date, travel.end_date):
            await msg.answer(
                f"❌ Ошибка: дата посещения выходит за пределы путешествия\n"
                f"📅 Путешествие: {travel.start_date.strftime('%d.%m.%Y')} - {travel.end_date.strftime('%d.%m.%Y')}\n"
                f"📅 Ваша дата: {visit_date.strftime('%d.%m.%Y')}"
            )
            return

        entry = Entry(
            travel_id=data["travel_id"],
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=datetime.strptime(data["visitation_date"], "%d.%m.%Y"),
            latitude=msg.location.latitude,
            longitude=msg.location.longitude
        )
        user = session.query(User).filter_by(tg_id=msg.from_user.id).first()
        session.add(entry)
        session.commit()
        await state.update_data(place_id=entry.place_id)

        new_achievements = check_achievements(user, session)
        session.commit()

        for ach in new_achievements:
            await msg.answer(
                f'🏆 <b>Новое достижение!</b>\n\n<b>{ach.achievement_name}</b>\n{ach.description}',
                parse_mode='HTML'
            )
    except Exception as e:
        print(f"❌ Ошибка сохранения геолокации: {e}")
        await msg.answer("❌ Ошибка при сохранении геолокации")
        return
    finally:
        session.close()

    await msg.answer(
        f"✅ Геолокация сохранена!\n"
        f"📍 Широта: {msg.location.latitude}\n"
        f"📍 Долгота: {msg.location.longitude}",
    )
    await msg.answer("📸 Хотите добавить фото или видео?", reply_markup=kb.type_media_keyboard)
    await state.set_state(EntryState.place_media)


@router.message(EntryState.location_manual)
async def handle_location_text_input(msg: Message, state: FSMContext):
    try:
        coords_text = msg.text.strip()

        # СОЗДАЕМ ПРОГРЕСС-БАР ВРУЧНУЮ
        progress_msg = await msg.answer("⏳ <b>Обработка координат</b>\n\n░░░░░░░░░░ 0%\n\n<i>Парсинг координат...</i>", parse_mode="HTML")

        # Шаг 1: Парсинг координат
        if ',' in coords_text:
            lat_str, lon_str = coords_text.split(',', 1)
        elif ' ' in coords_text:
            parts = coords_text.split()
            if len(parts) >= 2:
                lat_str, lon_str = parts[0], parts[1]
            else:
                await progress_msg.edit_text(
                    "❌ <b>Обработка координат прервана</b>\n\n"
                    "██████████ 100%\n\n"
                    "<i>Неверный формат. Нужно две координаты через пробел или запятую</i>",
                    parse_mode="HTML"
                )
                await msg.answer("❌ Неверный формат. Нужно две координаты через пробел или запятую")
                return
        else:
            await progress_msg.edit_text(
                "❌ <b>Обработка координат прервана</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Неверный формат координат</i>",
                parse_mode="HTML"
            )
            await msg.answer(
                "❌ Неверный формат координат.\n\n"
                "📌 Введите в формате:\n"
                "• <code>37.73778, 140.49753</code>\n"
                "• <code>37.73778 140.49753</code>\n\n"
                "📍 Или отправьте геолокацию через кнопку \"📎\"",
                parse_mode='HTML'
            )
            return

        # Шаг 2: Проверка координат
        await progress_msg.edit_text(
            "⏳ <b>Обработка координат</b>\n\n"
            "█████░░░░░ 50%\n\n"
            "<i>Проверка координат...</i>",
            parse_mode="HTML"
        )

        lat = float(lat_str.strip())
        lon = float(lon_str.strip())

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            await progress_msg.edit_text(
                "❌ <b>Обработка координат прервана</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Неверные координаты</i>",
                parse_mode="HTML"
            )
            await msg.answer(
                "❌ Неверные координаты:\n"
                "• Широта от -90 до 90\n"
                "• Долгота от -180 до 180"
            )
            return

        # Шаг 3: Сохранение данных
        await progress_msg.edit_text(
            "⏳ <b>Обработка координат</b>\n\n"
            "███████░░░ 70%\n\n"
            "<i>Сохранение данных...</i>",
            parse_mode="HTML"
        )

        # Используем локальную функцию сохранения
        success = await save_place_with_coordinates_local(msg, state, lat, lon)

        if success:
            # Шаг 4: Завершение
            await progress_msg.edit_text(
                "⏳ <b>Обработка координат</b>\n\n"
                "█████████░ 90%\n\n"
                "<i>Завершение операции...</i>",
                parse_mode="HTML"
            )

            await asyncio.sleep(0.5)

            # Финальное сообщение об успехе
            await progress_msg.edit_text(
                f"✅ <b>Обработка координат завершена!</b>\n\n"
                f"██████████ 100%\n\n"
                f"📍 Координаты сохранены: {lat:.5f}, {lon:.5f}\n\n"
                f"<i>Операция успешно выполнена</i> 🎉",
                parse_mode="HTML"
            )

            await msg.answer("📸 Хотите добавить фото или видео?", reply_markup=kb.type_media_keyboard)
            await state.set_state(EntryState.place_media)
        else:
            await progress_msg.edit_text(
                "❌ <b>Обработка координат прервана</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Ошибка при сохранении данных</i>",
                parse_mode="HTML"
            )

    except ValueError:
        try:
            await progress_msg.edit_text(
                "❌ <b>Обработка координат прервана</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Неверный числовой формат</i>",
                parse_mode="HTML"
            )
        except:
            pass
        await msg.answer(
            "❌ Неверный числовой формат.\n"
            "📌 Используйте числа как:\n"
            "<code>37.73778, 140.49753</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        try:
            await progress_msg.edit_text(
                "❌ <b>Обработка координат прервана</b>\n\n"
                "██████████ 100%\n\n"
                "<i>Произошла ошибка при выполнении</i>",
                parse_mode="HTML"
            )
        except:
            pass
        print(f"❌ Ошибка обработки координат: {e}")
        await msg.answer("❌ Ошибка при обработке координат. Попробуйте еще раз.")

@router.callback_query(F.data == "skip_coordinates")
async def skip_coordinates(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    session = Session()
    try:
        visit_date = datetime.strptime(data["visitation_date"], "%d.%m.%Y")
        travel = session.query(Travel).filter_by(travel_id=data["travel_id"]).first()

        if travel and not validate_date_within_travel(visit_date, travel.start_date, travel.end_date):
            await callback.message.answer(
                f"❌ Ошибка: дата посещения выходит за пределы путешествия\n"
                f"📅 Путешествие: {travel.start_date.strftime('%d.%m.%Y')} - {travel.end_date.strftime('%d.%m.%Y')}\n"
                f"📅 Ваша дата: {visit_date.strftime('%d.%m.%Y')}\n\n"
                "Вернитесь и введите корректную дату."
            )
            return

        entry = Entry(
            travel_id=data["travel_id"],
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=datetime.strptime(data["visitation_date"], "%d.%m.%Y"),
            latitude=None,  # Без координат
            longitude=None
        )
        session.add(entry)
        session.commit()
        await state.update_data(place_id=entry.place_id)

        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        new_achievements = check_achievements(user, session)
        session.commit()

        for ach in new_achievements:
            await callback.message.answer(
                f'🏆 <b>Новое достижение!</b>\n\n<b>{ach.achievement_name}</b>\n{ach.description}',
                parse_mode='HTML'
            )

    except Exception as e:
        print(f"❌ Ошибка сохранения без координат: {e}")
        await callback.message.answer("❌ Ошибка при сохранении")
        return
    finally:
        session.close()

    await callback.message.answer("✅ Место сохранено без координат.")
    await callback.message.answer("📸 Хотите добавить фото или видео?", reply_markup=kb.type_media_keyboard)
    await state.set_state(EntryState.place_media)

@router.message(EntryState.place_rating)
async def place_rating_input(msg: Message, state: FSMContext):
    if not validate_rating(msg.text):
        await msg.answer("❌ Оценка должна быть числом от 1 до 10")
        return

    data = await state.get_data()
    session = Session()
    try:
        entry = session.query(Entry).filter_by(place_id=data['place_id']).first()
        entry.place_rating = int(msg.text)
        session.commit()
    finally:
        session.close()
    await msg.answer('📍 Хотите добавить еще одно место?', reply_markup=kb.finish_place_keyboard)
    await state.set_state(EntryState.another_place)

@router.message(EntryState.another_place)
async def another_place_input(msg: Message, state: FSMContext):
    await msg.answer('📍 Хотите добавить еще одно место или завершить запись о путешествии?', reply_markup=kb.finish_place_keyboard)

@router.callback_query(F.data == "another_place")
async def another_place(callback, state: FSMContext):
    await callback.answer()
    await callback.message.answer('📍 Отлично! Добавим еще одно место.\n🏙️ В каком городе?')
    await state.set_state(EntryState.city)