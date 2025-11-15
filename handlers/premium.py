from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter, Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ContentType
from sqlalchemy import func
from bot.travel_config import admin_id, card

from app.travel_session import Session
from app.travel_states import PremiumPayment
from app.travel_database import User, Travel, Entry, Media
import app.traveler_keyboard as kb
from app.travel_utils import rate_limiter, check_achievements

router = Router()

@router.callback_query(F.data == "premium_functions")
async def send_premium_functions(callback: CallbackQuery):
    premium_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Расширенная статистика", callback_data="premium_stats")],
        [InlineKeyboardButton(text="📅 Хронология путешествий", callback_data="premium_timeline")],
        [InlineKeyboardButton(text="🗺️ Умная heatmap", callback_data="premium_heatmap")],
        [InlineKeyboardButton(text="📈 Сравнительная аналитика", callback_data="premium_compare")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    premium_text = (
        "🌟 <b>ПРЕМИУМ ВОЗМОЖНОСТИ</b>\n\n"
        "• 📊 <b>Расширенная статистика</b> - детальная аналитика ваших путешествий\n"
        "• 📅 <b>Хронология</b> - активность по годам и месяцам\n"
        "• 🗺️ <b>Умная heatmap</b> - фильтры по рейтингу и датам\n"
        "• 📈 <b>Сравнительная аналитика</b> - прогресс за годы\n"
        "• 🏆 <b>Топы и рекорды</b> - ваши лучшие направления\n"
    )

    await callback.message.answer(premium_text, parse_mode="HTML", reply_markup=premium_keyboard)


@router.callback_query(F.data == "premium_stats")
async def premium_statistics(callback: CallbackQuery):
    if not rate_limiter.is_allowed(callback.from_user.id, "stats"):
        await callback.answer("❌ Слишком частые запросы статистики. Подождите 1 минуту.", show_alert=True)
        return

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user.premium:
            await callback.answer("❌ Только для премиум пользователей")
            return

        total_travels = session.query(
            Travel).filter_by(user_id=user.user_id).count()
        total_places = session.query(Entry).join(Travel).filter(Travel.user_id == user.user_id).count()
        total_photos = session.query(Media).join(Entry).join(Travel).filter(
            Travel.user_id == user.user_id,
            Media.media_type == 'photo'
        ).count()

        countries_stats = session.query(
            Travel.country,
            func.count(Travel.travel_id).label('visits')
        ).filter(Travel.user_id == user.user_id).group_by(Travel.country).order_by(
            func.count(Travel.travel_id).desc()).all()

        cities_stats = session.query(
            Entry.city,
            func.count(Entry.place_id).label('visits')
        ).join(Travel).filter(Travel.user_id == user.user_id).group_by(Entry.city).order_by(
            func.count(Entry.place_id).desc()).limit(10).all()

        avg_travel_rating = session.query(func.avg(Travel.travel_rating)).filter(
            Travel.user_id == user.user_id,
            Travel.travel_rating.isnot(None)
        ).scalar() or 0

        avg_place_rating = session.query(func.avg(Entry.place_rating)).join(Travel).filter(
            Travel.user_id == user.user_id,
            Entry.place_rating.isnot(None)
        ).scalar() or 0

        stats_text = (
            "📊 <b>ПРЕМИУМ СТАТИСТИКА</b>\n\n"
            f"• Всего путешествий: {total_travels}\n"
            f"• Посещенных мест: {total_places}\n"
            f"• Фотографий: {total_photos}\n"
            f"• Средняя оценка путешествий: {avg_travel_rating:.1f}⭐\n"
            f"• Средняя оценка мест: {avg_place_rating:.1f}⭐\n\n"
        )

        if countries_stats:
            stats_text += "<b>🏆 Топ стран:</b>\n"
            for country, visits in countries_stats[:5]:
                stats_text += f"• {country}: {visits} раз\n"
            stats_text += "\n"

        if cities_stats:
            stats_text += "<b>🏙️ Топ городов:</b>\n"
            for city, visits in cities_stats[:5]:
                stats_text += f"• {city}: {visits} мест\n"

        await callback.message.answer(stats_text, parse_mode="HTML", reply_markup=kb.back_to_menu_keyboard)

    finally:
        session.close()


@router.callback_query(F.data == "premium_timeline")
async def premium_timeline(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user.premium:
            await callback.answer("❌ Только для премиум пользователей")
            return

        travels_by_year = session.query(
            func.extract('year', Travel.start_date).label('year'),
            func.count(Travel.travel_id).label('count')
        ).filter(Travel.user_id == user.user_id).group_by('year').order_by('year').all()

        travels_by_month = session.query(
            func.extract('month', Travel.start_date).label('month'),
            func.count(Travel.travel_id).label('count')
        ).filter(Travel.user_id == user.user_id).group_by('month').order_by('month').all()

        timeline_text = "📅 <b>ХРОНОЛОГИЯ ПУТЕШЕСТВИЙ</b>\n\n"

        if travels_by_year:
            timeline_text += "<b>По годам:</b>\n"
            for year, count in travels_by_year:
                timeline_text += f"• {int(year)}: {int(count)} путешествий\n"
            timeline_text += "\n"

        if travels_by_month:
            month_names = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
            timeline_text += "<b>По месяцам (все года):</b>\n"
            for month, count in travels_by_month:
                timeline_text += f"• {month_names[int(month)]}: {int(count)}\n"

        await callback.message.answer(timeline_text, parse_mode="HTML", reply_markup=kb.back_to_menu_keyboard)

    finally:
        session.close()

@router.callback_query(F.data == "premium_check")
async def premium_check(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
    finally:
        session.close()

    if user.premium:
        days_left = (user.end_premium - datetime.now()).days
        text = (
            f"💎 <b>У вас активирован премиум</b>\n\n"
            f"📅 Действует до: {user.end_premium.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"✨ <b>Ваши премиум возможности:</b>\n"
            f"• 📊 Расширенная статистика\n"
            f"• 🗺️ Умные фильтры heatmap\n"
            f"• 📸 До 8 фото на место\n"
            f"• 🏆 Эксклюзивные достижения\n"
            f"• 📈 Сравнительная аналитика"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Премиум функции", callback_data="premium_functions")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
        ])
    else:
        text = (
            "🔓 <b>Премиум подписка</b>\n\n"
            "💫 <b>Откройте все возможности:</b>\n"
            "• 📊 Расширенная статистика и аналитика\n"
            "• 🗺️ Умные фильтры для heatmap\n"
            "• 📸 До 8 медиа на место (вместо 3)\n"
            "• 🏆 Эксклюзивные достижения\n"
            "• 📈 Сравнительная аналитика\n"
            "• 🎯 Персональные рекомендации\n\n"
            "💎 <b>Выберите тариф:</b>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 1 месяц - 299₽", callback_data="buy_premium:1_month")],
            [InlineKeyboardButton(text="💫 3 месяца - 799₽", callback_data="buy_premium:3_months")],
            [InlineKeyboardButton(text="🎁 1 год - 2499₽", callback_data="buy_premium:1_year")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
        ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("buy_premium:"))
async def buy_premium_manual(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]
    tariffs = {
        '1_month': {'price': '299₽', 'duration': '1 месяц', 'days': 30},
        '3_months': {'price': '799₽', 'duration': '3 месяца', 'days': 90},
        '1_year': {'price': '2499₽', 'duration': '1 год', 'days': 365}
    }

    tariff = tariffs.get(period)
    if not tariff:
        await callback.answer("❌ Неверный тариф")
        return

    payment_info = (
        f"💎 <b>Оформление премиум подписки</b>\n\n"
        f"📅 Тариф: {tariff['duration']}\n"
        f"💳 Стоимость: {tariff['price']}\n"
        f"⏳ Срок действия: {tariff['duration']}\n\n"
        f"<b>Способы оплаты:</b>\n"
        f"• 💳 Карта: <code>{card}</code>\n\n"
        f"<b>Инструкция:</b>\n"
        f"1. Совершите перевод на указанную карту\n"
        f"2. Нажмите кнопку '✅ Я оплатил(а)'\n"
        f"3. Отправьте скриншот чека/перевода\n\n"
        f"💰 <b>Акция:</b> При оплате от 3 месяцев - скидка 10%!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data=f"confirm_payment:{period}")],
        [InlineKeyboardButton(text="💬 Связаться с поддержкой", url="https://t.me/traveler_support_bot")],
        [InlineKeyboardButton(text="🔙 К выбору тарифа", callback_data="premium_check")]
    ])

    await callback.message.edit_text(payment_info, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_payment:"))
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]

    print(f"🔍 DEBUG: confirm_payment вызван, period={period}")

    tariffs = {
        '1_month': {'duration': '1 месяц', 'days': 30, 'price': '299₽'},
        '3_months': {'duration': '3 месяца', 'days': 90, 'price': '799₽'},
        '1_year': {'duration': '1 год', 'days': 365, 'price': '2499₽'}
    }

    tariff = tariffs.get(period)
    if not tariff:
        await callback.answer("❌ Неверный тариф")
        return

    # Сохраняем информацию о платеже в состоянии
    await state.update_data(
        premium_period=period,
        premium_duration=tariff['duration'],
        premium_days=tariff['days'],
        premium_price=tariff['price'],
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name
    )

    print(f"🔍 DEBUG: Данные сохранены в состоянии: user_id={callback.from_user.id}")

    confirmation_text = (
        f"✅ <b>Заявка на премиум принята!</b>\n\n"
        f"📅 Тариф: {tariff['duration']}\n"
        f"💳 Сумма: {tariff['price']}\n"
        f"⏳ Ожидайте активации в течение 24 часов\n\n"
        f"<b>Что делать дальше:</b>\n"
        f"1. 📸 <b>Отправьте скриншот оплаты</b> (фото чека или перевода)\n"
        f"2. ⏳ Ожидайте проверки платежа\n"
        f"3. 🔔 Получите уведомление об активации\n\n"
        f"<i>Просто отправьте фото скриншота в этот чат...</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отменить оплату", callback_data="premium_check")]
    ])

    await callback.message.edit_text(confirmation_text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(PremiumPayment.waiting_for_screenshot)
    await callback.answer()
    print("🔍 DEBUG: Состояние установлено: PremiumPayment.waiting_for_screenshot")

@router.message(StateFilter(PremiumPayment.waiting_for_screenshot), F.content_type == ContentType.PHOTO)
async def handle_payment_screenshot(message: Message, state: FSMContext):
    print("🔍 DEBUG: Начало обработки скриншота")

    data = await state.get_data()
    print(f"🔍 DEBUG: Данные состояния: {data}")

    # Получаем информацию о платеже
    period = data.get('premium_period')
    duration = data.get('premium_duration')
    days = data.get('premium_days')
    price = data.get('premium_price')
    user_id = data.get('user_id')
    username = data.get('username')
    first_name = data.get('first_name')

    print(f"🔍 DEBUG: user_id={user_id}, period={period}, days={days}")

    # Получаем file_id скриншота
    screenshot_file_id = message.photo[-1].file_id
    print(f"🔍 DEBUG: screenshot_file_id получен: {screenshot_file_id[:50]}...")

    # Формируем сообщение для админа
    admin_message = (
        f"💰 <b>НОВАЯ ЗАЯВКА НА ПРЕМИУМ</b>\n\n"
        f"👤 <b>Пользователь:</b>\n"
        f"• ID: <code>{user_id}</code>\n"
        f"• Имя: {first_name}\n"
        f"• Username: @{username if username else 'нет'}\n\n"
        f"💎 <b>Тариф:</b>\n"
        f"• Период: {duration}\n"
        f"• Дней: {days}\n"
        f"• Сумма: {price}\n\n"
        f"📅 <b>Для активации:</b>\n"
        f"<code>/activate_premium {user_id} {days}</code>"
    )

    print(f"🔍 DEBUG: Пытаемся отправить админу {admin_id}")

    try:
        # Отправляем админу сообщение со скриншотом
        success_count = 0
        for admin in [admin_id]:
            try:
                print(f"🔍 DEBUG: Отправка админу {admin}")
                await message.bot.send_photo(
                    chat_id=admin,
                    photo=screenshot_file_id,
                    caption=admin_message,
                    parse_mode="HTML"
                )
                success_count += 1
                print(f"✅ DEBUG: Сообщение админу {admin} отправлено успешно")
            except Exception as e:
                print(f"❌ DEBUG: Ошибка отправки админу {admin}: {e}")

        print(f"🔍 DEBUG: Успешно отправлено {success_count} админам")

        success_text = (
            f"✅ <b>Скриншот получен!</b>\n\n"
            f"📸 Ваш платеж передан на проверку.\n"
            f"⏳ Обычно проверка занимает до 24 часов.\n\n"
            f"💎 <b>Детали заявки:</b>\n"
            f"• Тариф: {duration}\n"
            f"• Сумма: {price}\n"
            f"• Срок: {days} дней\n\n"
            f"🔔 Вы получите уведомление сразу после активации премиума!"
        )

        await message.answer(success_text, parse_mode="HTML", reply_markup=kb.back_to_menu_keyboard)

    except Exception as e:
        print(f"❌ Ошибка обработки скриншота: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке скриншота. Попробуйте еще раз или свяжитесь с поддержкой.",
            reply_markup=kb.back_to_menu_keyboard
        )

    await state.clear()
    print("🔍 DEBUG: Состояние очищено")


@router.message(Command("activate_premium"))
async def activate_premium_admin(message: Message):
    if message.from_user.id not in [admin_id]:
        await message.answer("❌ Недостаточно прав")
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /activate_premium user_id days")
            return

        user_id = int(parts[1])
        days = int(parts[2])

        session = Session()
        user = session.query(User).filter_by(tg_id=user_id).first()

        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        from datetime import datetime, timedelta
        user.premium = True
        user.end_premium = datetime.now() + timedelta(days=days)

        new_achievements = check_achievements(user, session)

        session.commit()

        # Уведомление админа
        await message.answer(
            f"✅ Премиум активирован для пользователя {user.name}\n"
            f"📅 До: {user.end_premium.strftime('%d.%m.%Y')}\n"
            f"🏆 Новых достижений: {len(new_achievements)}"
        )

        # Уведомление пользователя через message.bot
        try:
            await message.bot.send_message(
                user_id,
                f"🎉 <b>Ваш премиум активирован!</b>\n\n"
                f"💎 Срок действия: {days} дней\n"
                f"📅 До: {user.end_premium.strftime('%d.%m.%Y')}\n\n"
                f"✨ <b>Теперь вам доступны:</b>\n"
                f"• 📊 Расширенная статистика\n"
                f"• 🗺️ Умные фильтры heatmap\n"
                f"• 📸 До 8 фото на место\n"
                f"• 🏆 Эксклюзивные достижения\n\n"
                f"Наслаждайтесь премиум функциями! 🚀",
                parse_mode="HTML",
                reply_markup=kb.back_to_menu_keyboard
            )
        except Exception as e:
            print(f"❌ Не удалось уведомить пользователя: {e}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()


@router.message(StateFilter(PremiumPayment.waiting_for_screenshot))
async def handle_wrong_screenshot_type(message: Message):
    """Обработка неправильного типа сообщения (не фото)"""
    await message.answer(
        "❌ Пожалуйста, отправьте <b>скриншот оплаты</b> в виде фото.\n\n"
        "📸 Сделайте скриншот чека или перевода и отправьте его как фото.",
        parse_mode="HTML"
    )


@router.callback_query(StateFilter(PremiumPayment.waiting_for_screenshot), F.data == "premium_check")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ Оплата отменена")
    await callback.message.edit_text(
        "💎 <b>Оформление премиума отменено</b>\n\n"
        "Вы можете вернуться к выбору тарифа в любое время.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Выбрать тариф", callback_data="premium_check")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    )