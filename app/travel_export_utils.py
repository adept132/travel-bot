import asyncio
import io
import zipfile
from datetime import datetime
from aiogram import Bot
from sqlalchemy.orm import Session
from app.travel_database import User, Travel, Entry, Media


async def download_photo(bot: Bot, file_id: str) -> bytes:
    try:
        photo_file = await bot.get_file(file_id)
        photo_data = await bot.download_file(photo_file.file_path)
        return photo_data.read()
    except Exception as e:
        print(f"❌ Ошибка скачивания фото {file_id}: {e}")
        return None


async def create_zip_with_photos(
        bot: Bot,
        user_tg_id: int,
        session: Session,
        progress_callback=None
) -> tuple[io.BytesIO, int]:
    """Создает ZIP архив с фотографиями и возвращает (buffer, photo_count)"""
    user = session.query(User).filter_by(tg_id=user_tg_id).first()
    if not user:
        return None, 0

    zip_buffer = io.BytesIO()
    photo_counter = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Создаем README
        zip_file.writestr("README.txt", create_readme(user))

        if progress_callback:
            await progress_callback(photo_counter, "Подготовка структуры архива")

        # 2. Собираем все фото сначала для подсчета
        all_photos = []
        travels = session.query(Travel).filter_by(user_id=user.user_id).all()

        for travel in travels:
            entries = session.query(Entry).filter_by(travel_id=travel.travel_id).all()
            for entry in entries:
                photos = session.query(Media).filter_by(place_id=entry.place_id, media_type='photo').all()
                for photo in photos:
                    all_photos.append((photo, entry, travel))

        # 3. Скачиваем фото с прогрессом
        downloaded_photos = []
        for i, (photo, entry, travel) in enumerate(all_photos):
            if progress_callback:
                await progress_callback(i + 1, f"Скачивание фото {i + 1}/{len(all_photos)}")

            photo_data = await download_photo(bot, photo.file_id)
            if photo_data:
                downloaded_photos.append((photo_data, entry, travel, i))
                photo_counter += 1

            await asyncio.sleep(0.1)  # Задержка между запросами

        if progress_callback:
            await progress_callback(len(all_photos), "Создание HTML отчета")

        # 4. Создаем HTML с скачанными фото
        html_content = await create_html_with_downloaded_photos(user, session, downloaded_photos, zip_file)
        zip_file.writestr("my_travels.html", html_content)

        # 5. Добавляем текстовый отчет
        text_content = create_text_report(user, session)
        zip_file.writestr("my_travels.txt", text_content)

    zip_buffer.seek(0)
    return zip_buffer, photo_counter


async def create_html_with_downloaded_photos(user: User, session: Session, downloaded_photos: list,
                                             zip_file: zipfile.ZipFile) -> str:
    """Создает HTML отчет с уже скачанными фото"""
    travels = session.query(Travel).filter_by(user_id=user.user_id).all()

    # Группируем фото по entry_id для удобства
    photos_by_entry = {}
    for photo_data, entry, travel, index in downloaded_photos:
        if entry.place_id not in photos_by_entry:
            photos_by_entry[entry.place_id] = []
        photos_by_entry[entry.place_id].append((photo_data, entry, index))

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Путешествия {user.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            .travel {{ border: 2px solid #e0e0e0; padding: 20px; margin: 25px 0; border-radius: 12px; background: #fafafa; }}
            .place {{ background: white; padding: 15px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #4CAF50; }}
            .photos {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }}
            .photo-container {{ text-align: center; }}
            .photo {{ max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #ddd; }}
            .photo-caption {{ font-size: 12px; color: #666; margin-top: 5px; }}
            .rating {{ color: #FF9800; font-weight: bold; }}
            .date {{ color: #757575; }}
            .country-header {{ color: #1976D2; border-bottom: 2px solid #1976D2; padding-bottom: 10px; }}
            .stats {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1 class="country-header">🗺️ Мои путешествия - {user.name}</h1>
        <div class="stats">
            <p><b>📅 Архив создан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <p><b>📊 Всего путешествий:</b> {len(travels)}</p>
            <p><b>🖼️ Фотографий в архиве:</b> {len(downloaded_photos)}</p>
        </div>
    """

    # Добавляем фото в ZIP и создаем HTML
    for travel in travels:
        entries = session.query(Entry).filter_by(travel_id=travel.travel_id).all()

        html += f"""
        <div class="travel">
            <h2>🌍 {travel.country}</h2>
            <p><b>📅 Даты:</b> {travel.start_date} - {travel.end_date}</p>
            <p><b>⭐ Оценка путешествия:</b> <span class="rating">{travel.travel_rating or 'Не оценено'}/10</span></p>
            <p><b>💬 Комментарий:</b> {travel.travel_comment or 'Без комментария'}</p>
        """

        for entry in entries:
            html += f"""
            <div class="place">
                <h3>📍 {entry.place_title} - {entry.city}</h3>
                <p class="date">📅 {entry.date}</p>
                <p><b>⭐ Оценка места:</b> <span class="rating">{entry.place_rating or 'Не оценено'}/10</span></p>
                <p><b>💬 Комментарий:</b> {entry.place_comment or 'Без комментария'}</p>
            """

            # Добавляем фотографии этого места
            entry_photos = photos_by_entry.get(entry.place_id, [])
            if entry_photos:
                html += f'<div class="photos">'

                for photo_data, entry_obj, photo_index in entry_photos:
                    photo_filename = f"photos/{photo_index:04d}_{entry.place_title}.jpg"
                    zip_file.writestr(photo_filename, photo_data)

                    html += f"""
                    <div class="photo-container">
                        <img src="{photo_filename}" class="photo" alt="{entry.place_title}">
                        <div class="photo-caption">Фото {photo_index + 1}</div>
                    </div>
                    """

                html += '</div>'
            else:
                html += '<p><i>📷 Фотографий этого места нет в архиве</i></p>'

            html += "</div>"  # закрываем place

        html += "</div>"  # закрываем travel

    html += """
    </body>
    </html>
    """

    return html


async def create_html_report(bot: Bot, user: User, session: Session, zip_file: zipfile.ZipFile) -> str:
    travels = session.query(Travel).filter_by(user_id=user.user_id).all()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Путешествия {user.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            .travel {{ border: 2px solid #e0e0e0; padding: 20px; margin: 25px 0; border-radius: 12px; background: #fafafa; }}
            .place {{ background: white; padding: 15px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #4CAF50; }}
            .photos {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }}
            .photo-container {{ text-align: center; }}
            .photo {{ max-width: 300px; max-height: 200px; border-radius: 8px; border: 1px solid #ddd; }}
            .photo-caption {{ font-size: 12px; color: #666; margin-top: 5px; }}
            .rating {{ color: #FF9800; font-weight: bold; }}
            .date {{ color: #757575; }}
            .country-header {{ color: #1976D2; border-bottom: 2px solid #1976D2; padding-bottom: 10px; }}
        </style>
    </head>
    <body>
        <h1 class="country-header">🗺️ Мои путешествия - {user.name}</h1>
        <p>📅 Архив создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        <p>📊 Всего путешествий: {len(travels)}</p>
    """

    photo_counter = 0

    for travel in travels:
        entries = session.query(Entry).filter_by(travel_id=travel.travel_id).all()

        html += f"""
        <div class="travel">
            <h2>🌍 {travel.country}</h2>
            <p><b>📅 Даты:</b> {travel.start_date} - {travel.end_date}</p>
            <p><b>⭐ Оценка путешествия:</b> <span class="rating">{travel.travel_rating or 'Не оценено'}/10</span></p>
            <p><b>💬 Комментарий:</b> {travel.travel_comment or 'Без комментария'}</p>
        """

        for entry in entries:
            html += f"""
            <div class="place">
                <h3>📍 {entry.place_title} - {entry.city}</h3>
                <p class="date">📅 {entry.date}</p>
                <p><b>⭐ Оценка места:</b> <span class="rating">{entry.place_rating or 'Не оценено'}/10</span></p>
                <p><b>💬 Комментарий:</b> {entry.place_comment or 'Без комментария'}</p>
            """

            photos = session.query(Media).filter_by(place_id=entry.place_id, media_type='photo').all()
            if photos:
                html += '<div class="photos">'

                for i, photo in enumerate(photos):
                    photo_data = await download_photo(bot, photo.file_id)
                    if photo_data:
                        photo_filename = f"photos/{photo_counter:04d}_{entry.place_title}_{i + 1}.jpg"
                        zip_file.writestr(photo_filename, photo_data)

                        html += f"""
                        <div class="photo-container">
                            <img src="{photo_filename}" class="photo" alt="{entry.place_title}">
                            <div class="photo-caption">Фото {i + 1}</div>
                        </div>
                        """

                        photo_counter += 1
                        await asyncio.sleep(0.1)

                html += '</div>'
            else:
                html += '<p><i>📷 Фотографий этого места нет</i></p>'

            html += "</div>"

        html += "</div>"

    html += f"""
        <div style="margin-top: 40px; padding: 20px; background: #e3f2fd; border-radius: 10px;">
            <h3>📊 Статистика архива</h3>
            <p>🖼️ Всего фотографий: {photo_counter}</p>
            <p>🌍 Путешествий: {len(travels)}</p>
            <p>📍 Мест: {sum(len(session.query(Entry).filter_by(travel_id=t.travel_id).all()) for t in travels)}</p>
        </div>
    </body>
    </html>
    """

    return html


def create_text_report(user: User, session: Session) -> str:
    """Создает текстовый отчет"""
    travels = session.query(Travel).filter_by(user_id=user.user_id).all()

    content = f"🚗 АРХИВ ПУТЕШЕСТВИЙ - {user.name}\n"
    content += "=" * 60 + "\n\n"
    content += f"📅 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

    total_photos = 0
    total_places = 0

    for travel in travels:
        entries = session.query(Entry).filter_by(travel_id=travel.travel_id).all()
        travel_photos = 0

        content += f"🌍 {travel.country}\n"
        content += f"   📅 {travel.start_date} - {travel.end_date}\n"
        content += f"   ⭐ Оценка: {travel.travel_rating or 'Не оценено'}/10\n"
        content += f"   💬 {travel.travel_comment or 'Без комментария'}\n\n"

        for entry in entries:
            photos_count = session.query(Media).filter_by(
                place_id=entry.place_id,
                media_type='photo'
            ).count()
            travel_photos += photos_count

            content += f"   📍 {entry.place_title} - {entry.city}\n"
            content += f"      📅 {entry.date} | ⭐ {entry.place_rating or 'Не оценено'}/10\n"
            content += f"      💬 {entry.place_comment or 'Без комментария'}\n"
            content += f"      🖼️ Фото: {photos_count}\n\n"

        content += f"   📊 Итого по поездке: {len(entries)} мест, {travel_photos} фото\n"
        content += "   " + "─" * 40 + "\n\n"

        total_photos += travel_photos
        total_places += len(entries)

    content += "=" * 60 + "\n"
    content += f"📈 ОБЩАЯ СТАТИСТИКА:\n"
    content += f"   🌍 Путешествий: {len(travels)}\n"
    content += f"   📍 Мест: {total_places}\n"
    content += f"   🖼️ Фотографий: {total_photos}\n"

    return content


def create_readme(user: User) -> str:
    """Создает README файл"""
    return f"""
АРХИВ ПУТЕШЕСТВИЙ {user.name}

СОДЕРЖАНИЕ АРХИВА:
──────────────────
• my_travels.html   - главный файл с фотографиями (открыть в браузере)
• my_travels.txt    - текстовый отчет
• photos/           - папка со всеми фотографиями
• README.txt        - этот файл

КАК ПОСМОТРЕТЬ:
──────────────
1. Распакуйте архив в отдельную папку
2. Откройте файл my_travels.html в любом браузере
3. Все фотографии будут отображаться автоматически

ВАЖНО:
──────
• Не перемещайте и не переименовывайте папку photos/
• Все файлы должны оставаться в одной папке
• Для лучшего просмотра используйте современные браузеры (Chrome, Firefox, Edge)

Создано Travel Bot 🤖
"""