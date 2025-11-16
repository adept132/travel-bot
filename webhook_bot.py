import os
import logging
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from bot.Traveler_bot import bot, dp, setup_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot):
    webhook_url = f"{os.getenv('RENDER_EXTERNAL_URL')}/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"✅ Webhook set to: {webhook_url}")


async def on_shutdown(bot):
    await bot.delete_webhook()
    logger.info("❌ Webhook deleted")


async def healthz(request):
    return web.Response(text="OK")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get('/healthz', healthz)

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
    import asyncio

    asyncio.run(setup_bot())
    main()