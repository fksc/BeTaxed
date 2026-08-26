from app.routers.certificates import router as certificates_router
from app.routers.intakes import router as intakes_router
from app.routers.invoices import router as invoices_router
from app.routers.me import router as me_router
from app.routers.members import router as members_router
from app.routers.notifications import router as notifications_router
from app.routers.ops import router as ops_router
from app.routers.people import router as people_router
from app.routers.ss_batches import router as ss_batches_router
from app.routers.webhooks import router as webhooks_router

__all__ = [
    "certificates_router",
    "intakes_router",
    "invoices_router",
    "me_router",
    "members_router",
    "notifications_router",
    "ops_router",
    "people_router",
    "ss_batches_router",
    "webhooks_router",
]
