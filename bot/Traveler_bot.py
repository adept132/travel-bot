import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from handlers.reminder import send_reminders
from aiogram import Bot, Dispatcher
from bot.config import token
from app.travel_session import engine
from app.travel_database import Base
from app.travel_scheduler import premium_management_scheduler
from aiogram.types import ErrorEvent, Message, CallbackQuery
from datetime import datetime, timedelta
from handlers import routers
from app.travel_utils import rate_limiter

bot = Bot(token=token)
dp = Dispatcher()


async def global_error_handler(event: ErrorEvent):
    logger = logging.getLogger(__name__)
    logger.error(f"Global error: {event.exception}", exc_info=True)

    try:
        if event.update.message:
            await event.update.message.answer("❌ Произошла ошибка. Попробуйте снова.")
        elif event.update.callback_query:
            await event.update.callback_query.answer("❌ Произошла ошибка. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

    return True


class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.default_limits = {
            "default": {"max_requests": 20, "time_window": 60},
            "heatmap": {"max_requests": 6, "time_window": 300},
            "media_upload": {"max_requests": 20, "time_window": 120},
            "stats": {"max_requests": 10, "time_window": 60},
            "export": {"max_requests": 2, "time_window": 300},
        }

    def is_allowed(self, user_id: int, category: str = "default", max_requests: int = None, window_seconds: int = None):
        if max_requests is None or window_seconds is None:
            category_limits = self.default_limits.get(category, self.default_limits["default"])
            max_requests = category_limits["max_requests"]
            window_seconds = category_limits["time_window"]

        now = datetime.now()
        key = f"{user_id}:{category}"

        if key not in self.requests:
            self.requests[key] = []

        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < timedelta(seconds=window_seconds)
        ]

        if len(self.requests[key]) >= max_requests:
            return False

        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()
heatmap_limiter = RateLimiter()
export_limiter = RateLimiter()


async def rate_limit_middleware(handler, event, data):
    user_id = None
    if hasattr(event, 'from_user') and event.from_user:
        user_id = event.from_user.id

    if user_id:
        if isinstance(event, Message):
            action = "message"
            max_requests = 30
        elif isinstance(event, CallbackQuery):
            action = "callback"
            max_requests = 60
        else:
            action = "other"
            max_requests = 20

        if not rate_limiter.is_allowed(user_id, action, max_requests):
            if isinstance(event, Message):
                await event.answer("❌ Слишком много запросов. Подождите 1 минуту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Слишком много действий. Подождите немного.", show_alert=True)
            return

    return await handler(event, data)


async def setup_bot():
    for router in routers:
        dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, 'cron', hour=12, minute=0, args=[bot])
    scheduler.start()

    dp.error.register(global_error_handler)
    dp.message.middleware(rate_limit_middleware)
    dp.callback_query.middleware(rate_limit_middleware)

    Base.metadata.create_all(bind=engine)

    asyncio.create_task(premium_management_scheduler(bot))

    print("✅ Бот настроен и готов к работе!")


async def main_polling():
    await setup_bot()
    print("🔄 Запуск бота в режиме polling...")
    await dp.start_polling(bot)
