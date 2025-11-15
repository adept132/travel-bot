from aiohttp import web
import logging

logger = logging.getLogger(__name__)

async def health_check(request):
    return web.Response(text="OK")

def create_health_app():
    app = web.Application()
    app.router.add_get('/health', health_check)
    return app

if __name__ == "__main__":
    app = create_health_app()
    web.run_app(app, host="0.0.0.0", port=8080)