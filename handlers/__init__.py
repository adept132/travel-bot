from .start import router as start_router
from .travel import router as travel_router
from .entry import router as entries_router
from .media import router as media_router
from .menu import router as menu_router
from .achievement import router as achievements_router
from .premium import router as premium_router
from .export import router as export_router
from .report import router as reports_router
from .map import router as maps_router
from .reminder import router as reminder_router
from .search import router as search_router
from .quick_add import router as quick_add_router
from .admin import router as admin_router


routers = [
    start_router,
    travel_router,
    entries_router,
    media_router,
    menu_router,
    achievements_router,
    premium_router,
    export_router,
    reports_router,
    maps_router,
    reminder_router,
    search_router,
    quick_add_router,
    admin_router
]