from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.analysis.pipeline import migrate_schema
from app.api.routes import router
from app.api.system import router as system_router
from app.config import settings
from app.db import async_session, engine
from app.models import Base, Store

STORES_SEED = [
    ("maruhan_umeda", "マルハン梅田店"),
    ("kicona_amagasaki", "キコーナ尼崎本店"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema(engine)

    async with async_session() as db:
        for store_id, name in STORES_SEED:
            existing = await db.get(Store, store_id)
            if not existing:
                db.add(Store(id=store_id, name=name, is_active=True))
        await db.commit()

    yield
    await engine.dispose()


app = FastAPI(
    title="Helix Victory API",
    description="店舗特化型 高期待値抽出エンジン",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(system_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/combat")
async def health_combat():
    """実戦ヘルス（E2E・監視用 — /api/v1/health/combat と同等）"""
    from app.analysis.recovery_engine import check_system_health

    return await check_system_health()
