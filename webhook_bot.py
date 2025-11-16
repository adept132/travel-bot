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
                endpoints = ['/', '/healthz', '/health']
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{app_url}{endpoint}", timeout=5) as resp:
                            logger.info(f"🔄 Ping {endpoint}: {resp.status}")
                    except:
                        pass
        except Exception as e:
            logger.error(f"❌ Keep-alive error: {e}")

        await asyncio.sleep(120)


async def healthz(request):
    return web.Response(text="OK")


async def root_handler(request):
    return web.Response(text="Travel Bot is running!")


async def create_app():
    app = web.Application()

    # Регистрируем обработчики
    app.router.add_get('/', root_handler)
    app.router.add_get('/healthz', healthz)
    app.router.add_get('/health', healthz)

    return app


async def main():
    try:
        logger.info("🔄 Setting up bot...")
        await setup_bot()

        app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://travel-bot-97vm.onrender.com')
        webhook_url = f"{app_url}/webhook"
        await bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook set to: {webhook_url}")

        asyncio.create_task(keep_alive())

        app = await create_app()

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        port = int(os.getenv('PORT', '8080'))
        logger.info(f"🚀 Webhook server starting on port {port}")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

        logger.info("✅ Server started successfully!")

        await asyncio.Future()

    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        raise


if __name__ == "__main__":
    # Запускаем асинхронную main функцию
    asyncio.run(main())