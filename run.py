import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot_owner.bot import main as owner_bot
from bot_client.bot import main as client_bot

async def main():
    await asyncio.gather(
        owner_bot(),
        client_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())