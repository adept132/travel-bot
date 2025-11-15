# handlers/admin.py
import asyncio
import psutil
import os
import sqlalchemy
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import desc

from bot.config import admin_id
from app.travel_session import Session
from app.travel_database import User, Travel, Entry

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == admin_id


def get_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="menu")]
        ]
    )


def get_admin_back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")]
        ]
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    session = Session()
    try:
        total_users = session.query(User).count()
        total_travels = session.query(Travel).count()
        total_entries = session.query(Entry).count()

        active_users = session.query(User).join(Travel).distinct().count()

        premium_users = session.query(User).filter(User.premium == True).count()

        stats_text = (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"🚀 Активных пользователей: <b>{active_users}</b>\n"
            f"💎 Премиум пользователей: <b>{premium_users}</b>\n"
            f"✈️ Всего путешествий: <b>{total_travels}</b>\n"
            f"📍 Всего записей: <b>{total_entries}</b>\n"
        )

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


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠️ <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_restart")
async def admin_restart(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, перезапустить", callback_data="admin_restart_confirm")
    builder.button(text="❌ Отмена", callback_data="admin_back")

    await callback.message.edit_text(
        "🔄 **Перезапуск бота**\n"
        "Бот будет перезапущен. Это займет несколько секунд.\n"
        "Подтвердите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_restart_confirm")
async def admin_restart_confirm(callback: CallbackQuery):
    await callback.message.edit_text("🔄 Перезапускаю бота...")

    import sys
    os.execv(sys.executable, ['python'] + sys.argv)


@router.callback_query(F.data == "admin_stop")
async def admin_stop(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🛑 Остановить", callback_data="admin_stop_confirm")
    builder.button(text="❌ Отмена", callback_data="admin_back")

    await callback.message.edit_text(
        "⏸️ **Остановка бота**\n"
        "Бот будет полностью остановлен.\n"
        "Для запуска потребуется ручное вмешательство.\n"
        "Подтвердите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_stop_confirm")
async def admin_stop_confirm(callback: CallbackQuery):
    await callback.message.edit_text("🛑 Останавливаю бота...")

    # Корректная остановка
    import signal
    os.kill(os.getpid(), signal.SIGTERM)


@router.callback_query(F.data == "admin_cleanup")
async def admin_cleanup(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Очистить кеш", callback_data="admin_clean_cache")
    builder.button(text="📊 Сброс статистики", callback_data="admin_reset_stats")
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(1)

    await callback.message.edit_text(
        "🧹 **Очистка системы**\n"
        "Выберите тип очистки:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        log_file = "bot.log"
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-20:]  # Последние 20 строк
                logs = "".join(lines)
        else:
            logs = "Файл логов не найден"

        logs_text = f"📋 **Последние логи:**\n```\n{logs[-1000:]}\n```"

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Обновить", callback_data="admin_logs")
        builder.button(text="◀️ Назад", callback_data="admin_back")

        await callback.message.edit_text(logs_text, reply_markup=builder.as_markup())

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка чтения логов: {str(e)}", reply_markup=get_admin_keyboard())


def get_uptime() -> str:
    if hasattr(psutil, 'boot_time'):
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}д {hours}ч {minutes}м"
    return "Неизвестно"


@router.message(Command("stats"))
async def quick_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    session = Session()
    users_count = session.query(User).count()
    travels_count = session.query(Travel).count()
    places_count = session.query(Entry).count()
    session.close()

    await message.answer(
        f"📊 **Быстрая статистика:**\n"
        f"👥 Пользователи: {users_count}\n"
        f"🗺️ Путешествия: {travels_count}\n"
        f"📍 Места: {places_count}\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}"
    )


# Команда для проверки состояния БД
@router.message(Command("db_status"))
async def db_status(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        session = Session()
        session.execute("SELECT 1")

        tables = session.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()

        table_info = "\n".join([f"📋 {table[0]}" for table in tables])

        await message.answer(
            f"🗃️ **Статус базы данных:**\n"
            f"✅ Соединение активно\n"
            f"📊 Таблицы:\n{table_info}"
        )
        session.close()

    except Exception as e:
        await message.answer(f"❌ Ошибка БД: {str(e)}")


@router.message(Command("db_info"))
async def db_info(message: Message):
    import os

    db_url = os.getenv('DATABASE_URL', 'Не установлен')

    if db_url and '@' in db_url:
        masked_url = db_url.split('@')[0].split(':')
        if len(masked_url) >= 3:
            masked_url[2] = '***'
        db_url = ':'.join(masked_url) + '@' + db_url.split('@')[1]

    db_type = "PostgreSQL" if "postgres" in db_url else "SQLite"

    await message.answer(
        f"🗃️ **Информация о БД:**\n"
        f"📊 Тип: {db_type}\n"
        f"🔗 URL: {db_url}\n"
        f"💾 Сохранение: {'✅ Да' if db_type == 'PostgreSQL' else '⚠️ Нет'}"
    )