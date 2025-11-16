import os

from aiohttp import web


async def health_check(request):
    return web.Response(text="OK")

async def healthz(request):
    return web.Response(text="OK")

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/healthz', healthz)

    port = int(os.getenv('PORT', '10000'))
    print(f"🚀 Health server on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)