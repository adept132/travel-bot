from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram import Bot

from app.travel_session import Session
from app.travel_database import User, Media, Entry, Travel
from app.travel_export_utils import create_zip_with_photos
from app.travel_utils import export_limiter, progress_manager, rate_limiter
import app.traveler_keyboard as kb

router = Router()

@router.callback_query(F.data == "export_menu")
async def export_menu(callback: CallbackQuery):
    export_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 ПОЛНЫЙ АРХИВ (с фото)", callback_data="export_full_zip")],
        [InlineKeyboardButton(text="📱 Фото-отчет в чат", callback_data="export_telegram")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(
        "📤 <b>ЭКСПОРТ ДАННЫХ</b>\n\n"
        "Выберите тип экспорта:\n\n"
        "• <b>📦 Полный архив</b> - HTML + все фотографии\n"
        "• <b>📄 Текстовый отчет</b> - быстрый экспорт\n",
        parse_mode="HTML",
        reply_markup=export_keyboard
    )


@router.callback_query(F.data == "export_full_zip")
async def export_full_zip(callback: CallbackQuery, bot: Bot):
    if not rate_limiter.is_allowed(callback.from_user.id, "export"):
        await callback.answer("❌ Слишком частые запросы экспорта. Подождите 5 минут.", show_alert=True)
        return

    await callback.answer("🔄 Создаем полный архив с фотографиями...")

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return

        progress_msg = await callback.message.answer("⏳ Подготавливаем экспорт...")

        total_photos = session.query(Media).join(Entry).join(
            Travel).filter(
            Travel.user_id == user.user_id,
            Media.media_type == 'photo'
        ).count()

        await progress_manager.start_progress(
            bot,
            callback.from_user.id,
            "Создание архива с фото",
            progress_msg
        )

        await progress_manager.update_progress(
            bot,
            callback.from_user.id,
            "Создание архива с фото",
            10,
            "Сбор информации о путешествиях"
        )

        zip_buffer, actual_photo_count = await create_zip_with_photos(
            bot=bot,
            user_tg_id=callback.from_user.id,
            session=session,
            progress_callback=lambda p, s: update_export_progress(
                bot, callback.from_user.id, p, s, total_photos
            )
        )

        if not zip_buffer:
            await progress_manager.complete_progress(
                bot,
                callback.from_user.id,
                "Создание архива с фото",
                False
            )
            return

        await progress_manager.update_progress(
            bot,
            callback.from_user.id,
            "Создание архива с фото",
            90,
            "Формирование финального архива"
        )

        caption = (
            f"📦 <b>Полный архив ваших путешествий</b>\n\n"
            f"🖼️ <b>Фотографий в архиве:</b> {actual_photo_count}\n"
            f"📁 <b>Размер:</b> {len(zip_buffer.getvalue()) // 1024} КБ\n"
            f"💾 <b>Как открыть:</b>\n"
            f"1. Скачайте архив\n"
            f"2. Распакуйте в папку\n"
            f"3. Откройте <code>my_travels.html</code>\n\n"
            f"<i>Все фотографии включены в архив</i> 📸"
        )

        zip_file = BufferedInputFile(
            zip_buffer.getvalue(),
            filename=f"travels_{user.name}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        )

        await progress_manager.complete_progress(
            bot,
            callback.from_user.id,
            "Создание архива с фото",
            True,
            f"✅ Успешно экспортировано {actual_photo_count} фотографий"
        )

        await callback.message.answer_document(
            zip_file,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        await progress_manager.complete_progress(
            bot,
            callback.from_user.id,
            "Создание архива с фото",
            False
        )
        await callback.message.answer(f"❌ Ошибка создания архива: {str(e)}")
        print(f"Ошибка экспорта: {e}")
    finally:
        session.close()


async def update_export_progress(bot: Bot, user_id: int, current: int, step: str, total_photos: int):
    if total_photos > 0:
        percentage = 10 + int((current / total_photos) * 80)
        await progress_manager.update_progress(
            bot,
            user_id,
            "Создание архива с фото",
            percentage,
            f"{step} ({current}/{total_photos})"
        )
    else:
        await progress_manager.update_progress(
            bot,
            user_id,
            "Создание архива с фото",
            50,
            step
        )

@router.callback_query(F.data == "export_text_only")
async def export_text_only(callback: CallbackQuery):
    if not rate_limiter.is_allowed(callback.from_user.id, "export"):
        await callback.answer("❌ Слишком частые запросы экспорта. Подождите 5 минут.", show_alert=True)
        return

    await callback.answer("🔄 Формируем текстовый отчет...")

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return

        # Получаем все путешествия пользователя
        travels = session.query(Travel).filter_by(user_id=user.user_id).order_by(Travel.start_date).all()

        if not travels:
            await callback.message.answer("📭 У вас нет путешествий для экспорта")
            return

        text_report = f"📊 ОТЧЕТ О ПУТЕШЕСТВИЯХ\nПользователь: {user.name}\nДата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        text_report += "=" * 50 + "\n\n"

        total_places = 0
        total_photos = 0

        for travel in travels:
            # Считаем места и фото для этого путешествия
            places_count = session.query(Entry).filter_by(travel_id=travel.travel_id).count()
            photos_count = session.query(Media).join(Entry).filter(
                Entry.travel_id == travel.travel_id,
                Media.media_type == 'photo'
            ).count()

            total_places += places_count
            total_photos += photos_count

            # Информация о путешествии
            duration = (travel.end_date - travel.start_date).days if travel.end_date and travel.start_date else 0
            text_report += f"🌍 {travel.country}\n"
            text_report += f"📅 {travel.start_date.strftime('%d.%m.%Y')} - {travel.end_date.strftime('%d.%m.%Y') if travel.end_date else 'в процессе'}\n"
            text_report += f"⏱️ Длительность: {duration} дней\n"
            text_report += f"📍 Мест: {places_count}\n"
            text_report += f"📸 Фото: {photos_count}\n"
            text_report += f"⭐ Оценка: {travel.travel_rating or 'не оценено'}\n"

            if travel.travel_comment and travel.travel_comment != "-":
                text_report += f"💬 Комментарий: {travel.travel_comment}\n"

            # Получаем места для этого путешествия
            entries = session.query(Entry).filter_by(travel_id=travel.travel_id).order_by(Entry.date).all()
            if entries:
                text_report += "\n📍 Посещенные места:\n"
                for entry in entries:
                    text_report += f"  • {entry.city}: {entry.place_title}\n"
                    if entry.place_comment and entry.place_comment != "-":
                        text_report += f"    💬 {entry.place_comment}\n"
                    if entry.place_rating:
                        text_report += f"    ⭐ {entry.place_rating}/10\n"
                    text_report += f"    📅 {entry.date.strftime('%d.%m.%Y')}\n"

            text_report += "\n" + "=" * 50 + "\n\n"

        # Общая статистика
        text_report += f"📈 ОБЩАЯ СТАТИСТИКА:\n"
        text_report += f"✈️ Путешествий: {len(travels)}\n"
        text_report += f"🏛️ Всего мест: {total_places}\n"
        text_report += f"🖼️ Всего фото: {total_photos}\n"
        text_report += f"🌏 Стран: {len(set(t.country for t in travels))}\n"

        # Если отчет слишком длинный, разбиваем на части
        if len(text_report) > 4000:
            parts = [text_report[i:i + 4000] for i in range(0, len(text_report), 4000)]
            for i, part in enumerate(parts):
                await callback.message.answer(f"📄 Часть {i + 1}/{len(parts)}\n\n{part}")
        else:
            await callback.message.answer(text_report)

        await callback.message.answer(
            "✅ Текстовый отчет сформирован!",
            reply_markup=kb.back_to_menu_keyboard
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка создания текстового отчета: {str(e)}")
        print(f"Ошибка текстового экспорта: {e}")
    finally:
        session.close()