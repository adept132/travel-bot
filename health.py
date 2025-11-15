from aiohttp import web
import aiohttp
import asyncio
import os


async def health_check(request):
    return web.Response(text="OK")


async def self_ping():
    app_url = os.getenv('RENDER_EXTERNAL_URL')
    if app_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{app_url}/health", timeout=10) as resp:
                    print(f"Health check ping: {resp.status}")
        except Exception as e:
            print(f"Ping error: {e}")


async def start_ping(app):
    if os.getenv('RENDER'):
        async def ping_loop():
            while True:
                await asyncio.sleep(300)  # 5 минут
                await self_ping()

        asyncio.create_task(ping_loop())


def create_app():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.on_startup.append(start_ping)
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv('PORT', '8080'))
    host = os.getenv('HOST', '0.0.0.0')

    print(f"🚀 Starting health server on {host}:{port}")
    web.run_app(app, host=host, port=port)