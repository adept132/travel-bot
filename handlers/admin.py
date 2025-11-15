from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import desc, func
from app.travel_session import Session
from app.travel_database import User, Travel, Entry, Achievement

router = Router()

ADMIN_IDS = [1572180733]


def get_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="✈️ Путешествия", callback_data="admin_travels")],
            [InlineKeyboardButton(text="🏆 Достижения", callback_data="admin_achievements")],
            [InlineKeyboardButton(text="🔧 Управление", callback_data="admin_manage")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="menu")]
        ]
    )


def get_admin_back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )


def get_admin_manage_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="🔄 Пересчет статистики", callback_data="admin_recalc_stats")],
            [InlineKeyboardButton(text="🗑️ Очистка данных", callback_data="admin_cleanup")],
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return

    await message.answer(
        "🛠️ <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("admin_"))
async def check_admin_middleware(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа к админ-панели", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    session = Session()
    try:
        total_users = session.query(User).count()
        total_travels = session.query(Travel).count()
        total_entries = session.query(Entry).count()
        active_users = session.query(User).join(Travel).distinct().count()
        premium_users = session.query(User).filter(User.premium == True).count()

        total_achievements = session.query(Achievement).count()

        active_users_stats = session.query(
            User.name,
            func.count(Travel.travel_id).label('travel_count')
        ).join(Travel).group_by(User.user_id).order_by(desc('travel_count')).limit(5).all()

        stats_text = (
            "📊 <b>Общая статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"🚀 Активных пользователей: <b>{active_users}</b>\n"
            f"💎 Премиум пользователей: <b>{premium_users}</b>\n"
            f"✈️ Всего путешествий: <b>{total_travels}</b>\n"
            f"📍 Всего записей: <b>{total_entries}</b>\n"
            f"🏆 Всего достижений: <b>{total_achievements}</b>\n\n"
            "🏆 <b>Топ-5 активных пользователей:</b>\n"
        )

        for i, (name, count) in enumerate(active_users_stats, 1):
            stats_text += f"{i}. {name or 'Без имени'}: {count} путешествий\n"

        await callback.message.edit_text(
            stats_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при получении статистики: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )
    finally:
        session.close()


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    session = Session()
    try:
        users = session.query(User).order_by(desc(User.created_at)).limit(15).all()

        if not users:
            await callback.message.edit_text(
                "❌ Пользователи не найдены",
                reply_markup=get_admin_back_keyboard()
            )
            return

        users_text = "👥 <b>Последние 15 пользователей</b>\n\n"

        for i, user in enumerate(users, 1):
            user_travels = session.query(Travel).filter_by(user_id=user.user_id).count()
            premium_status = "💎" if user.premium else "🔹"
            created = user.created_at.strftime("%d.%m.%Y") if user.created_at else "N/A"

            users_text += (
                f"{i}. {premium_status} <b>{user.name or 'Без имени'}</b>\n"
                f"   ID: {user.tg_id} | 🛣️ {user_travels} путей\n"
                f"   📅 {created}\n\n"
            )

        await callback.message.edit_text(
            users_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при получении пользователей: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )
    finally:
        session.close()


@router.callback_query(F.data == "admin_travels")
async def admin_travels(callback: CallbackQuery):
    session = Session()
    try:
        travels = session.query(Travel).order_by(desc(Travel.created_at)).limit(10).all()

        if not travels:
            await callback.message.edit_text(
                "❌ Путешествия не найдены",
                reply_markup=get_admin_back_keyboard()
            )
            return

        travels_text = "✈️ <b>Последние 10 путешествий</b>\n\n"

        for i, travel in enumerate(travels, 1):
            user = session.query(User).filter_by(user_id=travel.user_id).first()
            user_name = user.name if user else "Неизвестно"
            entries_count = session.query(Entry).filter_by(travel_id=travel.travel_id).count()

            travels_text += (
                f"{i}. 🌍 <b>{travel.country}</b>\n"
                f"   👤 {user_name} | 📍 {entries_count} записей\n"
                f"   📅 {travel.start_date.strftime('%d.%m.%Y')} - {travel.end_date.strftime('%d.%m.%Y')}\n\n"
            )

        await callback.message.edit_text(
            travels_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при получении путешествий: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )
    finally:
        session.close()


@router.callback_query(F.data == "admin_achievements")
async def admin_achievements(callback: CallbackQuery):
    session = Session()
    try:
        achievements_stats = session.query(
            Achievement.achievement_name,
            func.count(Achievement.achievement_id).label('count')
        ).group_by(Achievement.achievement_name).all()

        total_achievements_given = session.query(Achievement).count()
        unique_users_with_achievements = session.query(Achievement.user_id).distinct().count()

        achievements_text = (
            "🏆 <b>Статистика достижений</b>\n\n"
            f"📊 Всего выдано достижений: <b>{total_achievements_given}</b>\n"
            f"👥 Уникальных пользователей с достижениями: <b>{unique_users_with_achievements}</b>\n\n"
            "📈 <b>Распределение по типам:</b>\n"
        )

        for achievement_name, count in achievements_stats:
            achievements_text += f"• {achievement_name}: {count}\n"

        await callback.message.edit_text(
            achievements_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при получении статистики достижений: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )
    finally:
        session.close()


@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔧 <b>Управление ботом</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_manage_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Функция в разработке...",
        reply_markup=get_admin_back_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_recalc_stats")
async def admin_recalc_stats(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔄 <b>Пересчет статистики</b>\n\n"
        "Функция в разработке...",
        reply_markup=get_admin_back_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_cleanup")
async def admin_cleanup(callback: CallbackQuery):
    await callback.message.edit_text(
        "🗑️ <b>Очистка данных</b>\n\n"
        "Функция в разработке...",
        reply_markup=get_admin_back_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠️ <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )