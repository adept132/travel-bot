from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.travel_session import Session
from app.travel_database import User, UserSettings, Travel, Entry
from app.travel_utils import rate_limiter
import app.traveler_keyboard as kb

router = Router()

@router.callback_query(F.data == "reminders_settings")
async def reminders_settings(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        settings = session.query(UserSettings).filter_by(user_id=user.user_id).first()
        if not settings:
            settings = UserSettings(user_id=user.user_id)
            session.add(settings)
            session.commit()

        status = "✅ Включены" if settings.reminders_enabled else "❌ Выключены"
        frequency = settings.reminder_frequency

        text = (
            "🔔 <b>Настройки напоминаний</b>\n\n"
            f"• Статус: {status}\n"
            f"• Частота: каждые {frequency} дней\n\n"
            "Напоминания помогут не забывать добавлять новые места в ваши путешествия!"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Выключить напоминания" if settings.reminders_enabled else "✅ Включить напоминания",
                callback_data="toggle_reminders"
            )],
            [InlineKeyboardButton(text="📅 Изменить частоту", callback_data="change_frequency")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        await callback.answer("❌ Ошибка загрузки настроек")
        print(f"Ошибка в reminders_settings: {e}")
    finally:
        session.close()

@router.callback_query(F.data == "toggle_reminders")
async def toggle_reminders(callback: CallbackQuery):
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        settings = session.query(UserSettings).filter_by(user_id=user.user_id).first()
        if not settings:
            settings = UserSettings(user_id=user.user_id)
            session.add(settings)

        settings.reminders_enabled = not settings.reminders_enabled
        session.commit()

        status = "включены" if settings.reminders_enabled else "выключены"
        await callback.answer(f"🔔 Напоминания {status}")
        await reminders_settings(callback)

    except Exception as e:
        await callback.answer("❌ Ошибка изменения настроек")
        print(f"Ошибка в toggle_reminders: {e}")
    finally:
        session.close()

@router.callback_query(F.data == "change_frequency")
async def change_frequency_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Каждые 3 дня", callback_data="set_frequency:3")],
        [InlineKeyboardButton(text="📅 Раз в неделю", callback_data="set_frequency:7")],
        [InlineKeyboardButton(text="📅 Раз в 2 недели", callback_data="set_frequency:14")],
        [InlineKeyboardButton(text="📅 Раз в месяц", callback_data="set_frequency:30")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="reminders_settings")]
    ])

    await callback.message.edit_text(
        "📅 <b>Выберите частоту напоминаний</b>\n\n"
        "Как часто вам напоминать о добавлении новых мест?",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("set_frequency:"))
async def set_frequency(callback: CallbackQuery):
    try:
        frequency = int(callback.data.split(":")[1])
    except ValueError:
        await callback.answer("❌ Неверная частота")
        return

    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        settings = session.query(UserSettings).filter_by(user_id=user.user_id).first()
        if not settings:
            settings = UserSettings(user_id=user.user_id)
            session.add(settings)

        settings.reminder_frequency = frequency
        session.commit()

        await callback.answer(f"✅ Частота установлена: {frequency} дней")
        await reminders_settings(callback)

    except Exception as e:
        await callback.answer("❌ Ошибка изменения частоты")
        print(f"Ошибка в set_frequency: {e}")
    finally:
        session.close()

async def send_reminders(bot):
    session = Session()
    try:
        users_with_reminders = session.query(User, UserSettings).join(
            UserSettings, User.user_id == UserSettings.user_id
        ).filter(
            UserSettings.reminders_enabled == True
        ).all()

        for user, settings in users_with_reminders:
            if settings.last_reminder_date:
                days_since_last = (datetime.now() - settings.last_reminder_date).days
                if days_since_last < settings.reminder_frequency:
                    continue

            last_travel = session.query(Travel).filter_by(
                user_id=user.user_id
            ).order_by(Travel.created_at.desc()).first()

            if last_travel:
                days_since_last_travel = (datetime.now() - last_travel.created_at).days
                if days_since_last_travel >= 30:
                    try:
                        await bot.send_message(
                            user.tg_id,
                            "🔔 <b>Напоминание о путешествиях</b>\n\n"
                            f"Прошло уже {days_since_last_travel} дней с вашего последнего путешествия!\n"
                            "Не забудьте добавить новые впечатления в ваш дневник путешественника 🗺️",
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="➕ Добавить место", callback_data="quick_add_place")]
                            ])
                        )
                        settings.last_reminder_date = datetime.now()
                        session.commit()
                    except Exception as e:
                        print(f"Не удалось отправить напоминание пользователю {user.tg_id}: {e}")

    except Exception as e:
        print(f"Ошибка в send_reminders: {e}")
    finally:
        session.close()