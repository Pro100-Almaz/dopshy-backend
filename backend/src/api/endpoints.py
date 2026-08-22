import fastapi

from src.api.routes.account import router as account_router
from src.api.routes.academy import router as academy_router
from src.api.routes.authentication import router as auth_router
from src.api.routes.boxing import router as boxing_router
from src.api.routes.booking import router as booking_router
from src.api.routes.bot_status import router as bot_status_router
from src.api.routes.field import router as field_router
from src.api.routes.football import router as football_router
from src.api.routes.history import router as history_router

router = fastapi.APIRouter()

router.include_router(router=account_router)
router.include_router(router=auth_router)
router.include_router(router=field_router)
router.include_router(router=booking_router)
router.include_router(router=bot_status_router)
router.include_router(router=academy_router)
router.include_router(router=boxing_router)
router.include_router(router=football_router)
router.include_router(router=history_router)
