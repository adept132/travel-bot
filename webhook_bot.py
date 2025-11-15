import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import token
from app.travel_session import engine
from app.travel_database import Base
from app.travel_scheduler import premium_management_scheduler
from handlers import routers
from bot.Traveler_bot import global_error_handler, rate_limit_middleware, RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-secret-token")  # Опционально


async def on_startup(bot: Bot, base_url: str):
    try:
        await bot.set_webhook(
            f"{base_url}{WEBHOOK_PATH}",
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook was set to: {base_url}{WEBHOOK_PATH}")

        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created")

        asyncio.create_task(premium_management_scheduler(bot))
        logger.info("✅ Premium management scheduler started")

    except Exception as e:
        logger.error(f"❌ Error during startup: {e}")


async def on_shutdown(bot: Bot):
    try:
        await bot.delete_webhook()
        logger.info("✅ Webhook was deleted")
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


def create_dispatcher():
    dp = Dispatcher()

    for router in routers:
        dp.include_router(router)

    dp.error.register(global_error_handler)

    dp.message.middleware(rate_limit_middleware)
    dp.callback_query.middleware(rate_limit_middleware)

    return dp


def create_app():
    bot = Bot(token=token)
    dp = create_dispatcher()

    app_name = os.getenv("FLY_APP_NAME", "your-app-name")
    base_url = f"https://{app_name}.fly.dev"

    dp.startup.register(lambda: on_startup(bot, base_url))
    dp.shutdown.register(lambda: on_shutdown(bot))

    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )

    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    from health import create_health_app
    health_app = create_health_app()
    app.add_subapp("/health/", health_app)

    async def root_health(request):
        return web.Response(text="Travel Bot is running! ✅")

    app.router.add_get('/', root_health)

    logger.info("✅ Webhook application created")
    return app


async def start_scheduler(bot: Bot):
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from handlers.reminder import send_reminders

        scheduler = AsyncIOScheduler()
        scheduler.add_job(send_reminders, 'cron', hour=12, minute=0, args=[bot])
        scheduler.start()
        logger.info("✅ Reminder scheduler started")
    except Exception as e:
        logger.error(f"❌ Error starting scheduler: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting Travel Bot in webhook mode...")

    app = create_app()

    bot = Bot(token=token)
    asyncio.create_task(start_scheduler(bot))

    web.run_app(
        app,
        host="0.0.0.0",
        port=8080,
        print=lambda *args: logger.info(" ".join(str(arg) for arg in args))
    )