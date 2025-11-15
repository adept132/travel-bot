import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from app.travel_session import Session
from app.travel_database import User
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

async def deactivate_expired_premium():
    session = Session()
    try:
        now = datetime.now()
        expired_users = session.query(User).filter(
            User.premium == True,
            User.end_premium <= now
        ).all()

        for user in expired_users:
            user.premium = False
            print(f"🔒 Деактивирован премиум для пользователя {user.tg_id}")

        if expired_users:
            session.commit()
            print(f"🔒 Деактивировано {len(expired_users)} просроченных премиумов")

    except Exception as e:
        print(f"❌ Ошибка деактивации премиумов: {e}")
    finally:
        session.close()

async def check_premium_expiry(bot: Bot):
    session = Session()
    try:
        now = datetime.now()
        expiring_users = session.query(User).filter(
            User.premium == True,
            User.end_premium <= now + timedelta(days=3),
            User.end_premium > now
        ).all()

        print(f"🔍 Проверка истекающих премиумов: найдено {len(expiring_users)} пользователей")

        for user in expiring_users:
            days_left = (user.end_premium - now).days
            try:
                await bot.send_message(
                    user.tg_id,
                    f"⚠️ <b>Премиум подписка истекает!</b>\n\n"
                    f"📅 Осталось дней: {days_left}\n"
                    f"💎 Действует до: {user.end_premium.strftime('%d.%m.%Y')}\n\n"
                    f"Продлите подписку чтобы сохранить все возможности!",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💎 Продлить премиум", callback_data="premium_check")]
                    ])
                )
                print(f"✅ Уведомление отправлено пользователю {user.tg_id}")
            except Exception as e:
                print(f"❌ Не удалось отправить уведомление пользователю {user.tg_id}: {e}")

    except Exception as e:
        print(f"❌ Ошибка в check_premium_expiry: {e}")
    finally:
        session.close()

async def premium_management_scheduler(bot: Bot):
    print("🚀 Запуск системы управления премиум подписками...")
    while True:
        try:
            await deactivate_expired_premium()
            await check_premium_expiry(bot)
            print("✅ Управление премиумами завершено, следующая проверка через 1 час")
        except Exception as e:
            print(f"❌ Ошибка в управлении премиумами: {e}")
        await asyncio.sleep(60 * 60)  # 1 час