from aiohttp import web
import aiohttp
import asyncio
import os

async def health_check(request):
    return web.Response(text=\"OK\")

async def self_ping():
    \"\"\"Автопинг чтобы инстанс не засыпал\"\"\"
    app_url = os.getenv('RENDER_EXTERNAL_URL')
    if app_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f\"{app_url}/health\", timeout=10) as resp:
                    print(f\"Health check ping: {resp.status}\")
        except Exception as e:
            print(f\"Ping error: {e}\")

async def start_ping(app):
    \"\"\"Запуск периодического пинга на Render\"\"\"
    if os.getenv('RENDER'):
        async def ping_loop():
            while True:
                await asyncio.sleep(300)  # 5 минут
                await self_ping()
        asyncio.create_task(ping_loop())

app = web.Application()
app.router.add_get('/health', health_check)
app.on_startup.append(start_ping)

if __name__ == \"__main__\":
    web.run_app(app, host='0.0.0.0', port=8080)
