import asyncio
import sys
import os
import uvicorn

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from bot_owner.bot import main as owner_bot
from api.main import app

async def start_api():
    config = uvicorn.Config(
        app       = app,
        host      = "0.0.0.0",
        port      = 8000,
        log_level = "warning"
    )
    server = uvicorn.Server(config)
    print("🌐 API запущен на http://localhost:8000")
    await server.serve()

async def main():
    await asyncio.gather(
        owner_bot(),
        start_api()
    )

if __name__ == "__main__":
    asyncio.run(main())