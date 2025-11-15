import asyncio
import os
import tempfile
from datetime import datetime, timedelta

import folium
from aiogram import F, Router
from aiogram.types import CallbackQuery, BufferedInputFile, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from folium.plugins import HeatMap
from sqlalchemy import func

from app.travel_session import Session
from app.travel_database import User, Travel, Entry
from app.travel_utils import rate_limiter, progress_manager, get_user_continents, CONTINENTS, normalize_country_name
import app.traveler_keyboard as kb
import selenium

router = Router()

@router.callback_query(F.data == "heatmap")
async def build_heatmap(callback: CallbackQuery):
    if not rate_limiter.is_allowed(callback.from_user.id, "heatmap"):
        await callback.answer("❌ Слишком частые запросы генерации карт. Подождите 5 минут.", show_alert=True)
        return
    await callback.answer("🔄 Начинаем генерацию карты...")
    original_message = callback.message

    session = Session()

    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.message.answer('⛔ Нет такого пользователя. Сначала создайте запись путешествия')
            return

        # Шаг 1: Начальный прогресс (редактируем исходное сообщение)
        await progress_manager.start_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            original_message
        )

        await asyncio.sleep(0.5)

        # Шаг 2: Получение записей
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            30,
            "Получение данных о местах"
        )

        entries = session.query(Entry).join(Travel, Entry.travel_id == Travel.travel_id) \
            .filter(Travel.user_id == user.user_id).all()

        points = []
        popups = []

        for e in entries:
            if e.latitude is not None and e.longitude is not None:
                points.append([float(e.latitude), float(e.longitude)])
                popups.append((float(e.latitude), float(e.longitude), f"{e.place_title} — {e.city}"))

        # Шаг 3: Проверка данных
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            50,
            f"Обработано {len(points)} мест"
        )

        if not points:
            await progress_manager.complete_progress(
                callback.bot,
                callback.from_user.id,
                "Генерация карты путешествий",
                False
            )
            return

        # Шаг 4: Создание карты
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            70,
            "Создание карты"
        )

        lats = [p[0] for p in points]
        lons = [p[1] for p in points]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        avg_lat = sum(lats) / len(lats)
        avg_lon = sum(lons) / len(lons)

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon

        # Определяем zoom level
        if lat_span == 0 and lon_span == 0:
            zoom_level = 12
        elif lat_span < 0.1 and lon_span < 0.1:
            zoom_level = 10
        elif lat_span < 0.5 and lon_span < 0.5:
            zoom_level = 8
        elif lat_span < 2 and lon_span < 2:
            zoom_level = 7
        elif lat_span < 10 and lon_span < 10:
            zoom_level = 6
        elif lat_span < 30 and lon_span < 30:
            zoom_level = 5
        else:
            zoom_level = 3

        if len(points) <= 3:
            zoom_level = min(zoom_level + 2, 15)
        elif len(points) <= 10:
            zoom_level = min(zoom_level + 1, 12)

        # Создаем карту
        m = folium.Map(
            location=[avg_lat, avg_lon],
            zoom_start=zoom_level,
            control_scale=True,
            tiles='CartoDB positron'
        )

        HeatMap(
            points,
            min_opacity=0.3,
            max_zoom=18,
            radius=15,
            blur=10,
            gradient={'0.4': 'blue', '0.6': 'lime', '0.8': 'orange', '1.0': 'red'}
        ).add_to(m)

        for lat, lon, text in popups:
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color='green',
                fill=True,
                fill_color='green',
                fill_opacity=0.6
            ).add_to(m)

        # Шаг 5: Генерация изображения
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            90,
            "Формирование изображения"
        )

        img_data = m._to_png(5)
        heatmap_file = BufferedInputFile(img_data, filename="travel_heatmap.png")

        # Завершаем прогресс
        await progress_manager.complete_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            True,
            f"📍 Обработано {len(points)} мест\n🌍 Создана тепловая карта"
        )

        # Отправляем результат как новое сообщение
        await callback.message.answer_photo(
            heatmap_file,
            caption=f"🌍 Ваша карта путешествий\n📍 {len(points)} локаций",
            reply_markup=kb.back_to_menu_keyboard
        )

    except Exception as e:
        print(f"❌ Ошибка в build_heatmap: {e}")
        await progress_manager.complete_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация карты путешествий",
            False
        )

        # Пробуем отправить HTML версию как запасной вариант
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                if 'm' in locals():
                    m.save(f.name)
                temp_file = f.name

            await callback.message.answer_document(
                FSInputFile(temp_file, filename="travel_heatmap.html"),
                caption=f"🌍 Ваша карта путешествий (HTML версия)\n📍 {len(points)} локаций"
            )
            os.unlink(temp_file)
        except Exception as html_error:
            await callback.message.answer(f"⛔ Ошибка создания карты: {str(e)}")

    finally:
        session.close()

@router.callback_query(F.data == "premium_heatmap_menu")
async def premium_heatmap_menu(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user.premium:
            await callback.answer("❌ Только для премиум пользователей")
            return

        filter_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Все места", callback_data="heatmap_all")],
            [InlineKeyboardButton(text="⭐ Только лучшие (8-10)", callback_data="heatmap_best")],
            [InlineKeyboardButton(text="📅 За последний год", callback_data="heatmap_recent")],
            [InlineKeyboardButton(text="🏆 Топ-10 по рейтингу", callback_data="heatmap_top10")],
            [InlineKeyboardButton(text="🗺️ По континентам", callback_data="heatmap_continents")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="premium_functions")]
        ])

        await callback.message.edit_text(
            "🗺️ <b>ПРЕМИУМ КАРТА</b>\n\n"
            "Выберите фильтр для heatmap:",
            parse_mode="HTML",
            reply_markup=filter_keyboard
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка в premium_heatmap_menu: {e}")
    finally:
        session.close()


@router.callback_query(F.data == "heatmap_continents")
async def choose_continent(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user.premium:
            await callback.answer("❌ Только для премиум пользователей")
            return

        # Получаем доступные континенты для пользователя
        available_continents = get_user_continents(user.user_id, session)

        if not available_continents:
            await callback.answer("❌ У вас нет данных по континентам")
            await callback.message.edit_text(
                "❌ <b>Нет данных по континентам</b>\n\n"
                "У вас пока нет путешествий в других континентах или мы не смогли определить "
                "принадлежность стран к континентам.\n\n"
                "💡 <i>Добавьте больше путешествий с указанием стран</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К фильтрам", callback_data="premium_heatmap")]
                ])
            )
            return

        # Создаем клавиатуру только с доступными континентами
        keyboard_buttons = []
        for continent_code in sorted(available_continents):
            continent_data = CONTINENTS[continent_code]
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=continent_data['name'],
                    callback_data=f"heatmap_continent:{continent_code}"
                )
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 К фильтрам", callback_data="premium_heatmap")
        ])

        continent_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            "🗺️ <b>Выберите континент</b>\n\n"
            "Отобразим только места из выбранного континента:",
            parse_mode="HTML",
            reply_markup=continent_keyboard
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка в choose_continent: {e}")
    finally:
        session.close()


@router.callback_query(F.data.startswith("heatmap_"))
async def generate_filtered_heatmap(callback: CallbackQuery):
    if not rate_limiter.is_allowed(callback.from_user.id, "heatmap"):
        await callback.answer("❌ Слишком частые запросы генерации карт. Подождите 5 минут.", show_alert=True)
        return
    await callback.answer("🔄 Начинаем генерацию карты...")

    original_message = callback.message
    session = Session()

    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user or not user.premium:
            await callback.message.answer("❌ Только для премиум пользователей")
            return

        filter_type = callback.data.replace("heatmap_", "")

        # Начинаем прогресс
        await progress_manager.start_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            original_message
        )

        await asyncio.sleep(0.5)

        # Шаг 2: Получение данных с правильной загрузкой связи
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            30,
            "Получение данных о местах"
        )

        # Базовый запрос с JOIN вместо joinedload
        query = session.query(Entry, Travel).join(Travel, Entry.travel_id == Travel.travel_id)
        query = query.filter(Travel.user_id == user.user_id)

        filter_description = "Все места"
        entries_data = []

        if filter_type == "all":
            filter_description = "Все места"
            entries_data = query.all()

        elif filter_type == "best":
            query = query.filter(Entry.place_rating >= 8)
            filter_description = "Лучшие места (8-10⭐)"
            entries_data = query.all()

        elif filter_type == "recent":
            one_year_ago = datetime.now() - timedelta(days=365)
            query = query.filter(Travel.start_date >= one_year_ago)
            filter_description = "За последний год"
            entries_data = query.all()

        elif filter_type == "top10":
            query = query.filter(Entry.place_rating.isnot(None)).order_by(Entry.place_rating.desc())
            filter_description = "Топ-10 по рейтингу"
            all_entries = query.all()
            entries_data = all_entries[:10]

        elif filter_type.startswith("continent:"):
            continent_code = filter_type.replace("continent:", "")
            continent = CONTINENTS.get(continent_code)

            if continent:
                # Получаем все страны пользователя
                user_countries = session.query(
                    func.distinct(Travel.country)
                ).filter(Travel.user_id == user.user_id).all()

                user_countries = [country[0] for country in user_countries if country[0]]

                # Находим страны пользователя, которые принадлежат к выбранному континенту
                matching_countries = []
                for user_country in user_countries:
                    normalized_user_country = normalize_country_name(user_country)
                    for continent_country in continent['countries']:
                        if normalized_user_country in normalize_country_name(continent_country):
                            matching_countries.append(user_country)
                            break

                print(f"🔍 Континент {continent_code}: найденные страны {matching_countries}")

                if matching_countries:
                    query = query.filter(Travel.country.in_(matching_countries))
                    filter_description = f"Континент: {continent['name']}"
                    entries_data = query.all()
                else:
                    # Если не нашли точных совпадений, пробуем частичное совпадение
                    all_entries_data = query.all()
                    filtered_entries = []
                    for entry, travel in all_entries_data:
                        if travel and travel.country:
                            normalized_country = normalize_country_name(travel.country)
                            if any(normalized_country in normalize_country_name(c) for c in continent['countries']):
                                filtered_entries.append((entry, travel))

                    entries_data = filtered_entries
                    if entries_data:
                        filter_description = f"Континент: {continent['name']} (автоопределение)"
                    else:
                        await progress_manager.complete_progress(
                            callback.bot,
                            callback.from_user.id,
                            "Генерация премиум карты",
                            False
                        )
                        await callback.message.answer(
                            f"❌ Не найдено мест в континенте {continent['name']}\n\n"
                            f"💡 <i>Добавьте путешествия в страны {continent['name']}</i>",
                            parse_mode="HTML"
                        )
                        return
            else:
                await callback.answer("❌ Континент не найден")
                return

        # Шаг 3: Обработка координат
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            50,
            f"Обработка {len(entries_data)} мест"
        )

        if not entries_data:
            await progress_manager.complete_progress(
                callback.bot,
                callback.from_user.id,
                "Генерация премиум карты",
                False
            )
            await callback.message.answer(
                "❌ Нет данных для отображения по выбранному фильтру\n\n"
                "💡 <i>Попробуйте другой фильтр или добавьте больше мест с координатами</i>",
                parse_mode="HTML"
            )
            return

        points = []
        popups = []

        for entry, travel in entries_data:
            if entry.latitude is not None and entry.longitude is not None:
                points.append([float(entry.latitude), float(entry.longitude)])
                rating_text = f" ({entry.place_rating}⭐)" if entry.place_rating else ""

                # Теперь travel доступен напрямую
                country_text = f", {travel.country}" if travel and travel.country else ""
                popup_text = f"{entry.place_title} — {entry.city}{country_text}{rating_text}"
                popups.append((float(entry.latitude), float(entry.longitude), popup_text))

        if not points:
            await progress_manager.complete_progress(
                callback.bot,
                callback.from_user.id,
                "Генерация премиум карты",
                False
            )
            await callback.message.answer(
                "❌ Нет мест с координатами для отображения\n\n"
                "💡 <i>Добавьте координаты к вашим местам для построения карты</i>",
                parse_mode="HTML"
            )
            return

        # Шаг 4: Создание карты
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            70,
            "Создание карты"
        )

        lats = [p[0] for p in points]
        lons = [p[1] for p in points]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        avg_lat = sum(lats) / len(lats)
        avg_lon = sum(lons) / len(lons)

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon

        # Определяем zoom level
        if lat_span == 0 and lon_span == 0:
            zoom_level = 12
        elif lat_span < 0.1 and lon_span < 0.1:
            zoom_level = 10
        elif lat_span < 0.5 and lon_span < 0.5:
            zoom_level = 8
        elif lat_span < 2 and lon_span < 2:
            zoom_level = 7
        elif lat_span < 10 and lon_span < 10:
            zoom_level = 6
        elif lat_span < 30 and lon_span < 30:
            zoom_level = 5
        else:
            zoom_level = 3

        if len(points) <= 3:
            zoom_level = min(zoom_level + 2, 15)
        elif len(points) <= 10:
            zoom_level = min(zoom_level + 1, 12)

        # Создаем карту
        m = folium.Map(
            location=[avg_lat, avg_lon],
            zoom_start=zoom_level,
            control_scale=True,
            tiles='CartoDB positron'
        )

        HeatMap(
            points,
            min_opacity=0.3,
            max_zoom=18,
            radius=15,
            blur=10,
            gradient={'0.4': 'blue', '0.6': 'lime', '0.8': 'orange', '1.0': 'red'}
        ).add_to(m)

        for lat, lon, text in popups:
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color='green',
                fill=True,
                fill_color='green',
                fill_opacity=0.6,
                popup=folium.Popup(text, max_width=250)
            ).add_to(m)

        # Шаг 5: Генерация изображения
        await progress_manager.update_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            90,
            "Формирование изображения"
        )

        img_data = m._to_png(5)
        heatmap_file = BufferedInputFile(img_data, filename=f"heatmap_{filter_type}.png")

        # Завершаем прогресс
        await progress_manager.complete_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            True,
            f"📍 Обработано {len(points)} мест\n🎯 Фильтр: {filter_description}"
        )

        # Отправляем результат как новое сообщение
        caption = f"🗺️ <b>Премиум Heatmap</b>\n📍 {filter_description}\n🔢 {len(points)} мест"

        nav_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Другой фильтр", callback_data="premium_heatmap")],
            [InlineKeyboardButton(text="🔙 В премиум меню", callback_data="premium_functions")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])

        await callback.message.answer_photo(
            heatmap_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=nav_keyboard
        )

    except Exception as e:
        await progress_manager.complete_progress(
            callback.bot,
            callback.from_user.id,
            "Генерация премиум карты",
            False
        )
        await callback.message.answer(f"❌ Ошибка создания heatmap: {str(e)}")
        print(f"Ошибка в filtered heatmap: {e}")
        import traceback
        traceback.print_exc()

    finally:
        session.close()

@router.callback_query(F.data == "premium_heatmap")
async def premium_heatmap_handler(callback: CallbackQuery):
    await callback.answer()
    await premium_heatmap_menu(callback)