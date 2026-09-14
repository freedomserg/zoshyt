"""FastAPI-застосунок. Запуск: uvicorn zoshyt.api.app:create_app --factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Збірка Mini App. Шлях відносно робочої теки процесу: локально — корінь
# репо (у dev теки нема, сторінку віддає Vite), у Docker — WORKDIR з dist.
MINIAPP_DIST = Path("miniapp/dist")


def create_app() -> FastAPI:
    app = FastAPI(title="Zoshyt", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        # select 1 до БД додасться разом із тестовою базою (крок 5 плану).
        return {"status": "ok"}

    # Роутери екранів (/api/*) — ПЕРЕД монтуванням статики: mount на "/"
    # перехоплює все, що не збіглося вище.
    if MINIAPP_DIST.is_dir():
        app.mount("/", StaticFiles(directory=MINIAPP_DIST, html=True), name="miniapp")

    return app
