import os
import logging
import aiohttp
import asyncio
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from bot.Traveler_bot import bot, dp, setup_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def keep_alive():
    app_url = os.getenv('RENDER_EXTERNAL_URL')
    if not app_url:
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{app_url}/healthz", timeout=10) as resp:
                    logger.info(f"🔄 Keep-alive ping: {resp.status}")
        except Exception as e:
            logger.error(f"❌ Keep-alive error: {e}")

        await asyncio.sleep(480)


async def on_startup(bot):
    webhook_url = f"{os.getenv('RENDER_EXTERNAL_URL')}/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"✅ Webhook set to: {webhook_url}")

    asyncio.create_task(keep_alive())


async def on_shutdown(bot):
    await bot.delete_webhook()
    logger.info("❌ Webhook deleted")


async def healthz(request):
    logger.info("🩺 Health-check received")
    return web.Response(text="OK")


async def root_handler(request):
    return web.Response(text="Travel Bot is running!")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get('/', root_handler)
    app.router.add_get('/healthz', healthz)
    app.router.add_get('/health', healthz)

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.getenv('PORT', '8080'))
    logger.info(f"🚀 Webhook server starting on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)


if __name__ == "__main__":
    # Сначала настраиваем бота, потом запускаем сервер
    import asyncio

    asyncio.run(setup_bot())
    main()