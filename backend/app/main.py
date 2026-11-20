from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Register model classes before creating the tables.
from app import models
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.shops import router as shops_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.db.database import engine
from app.db.init_db import ensure_admin_account, initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    initialize_database(engine)
    ensure_admin_account(engine)
    yield


app = FastAPI(title="KahveCell API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):[0-9]+$",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(payments_router)
app.include_router(orders_router)
app.include_router(shops_router)
app.include_router(subscriptions_router)


@app.get("/", response_class=PlainTextResponse)
def read_root() -> str:
    return "çalışıyor"
