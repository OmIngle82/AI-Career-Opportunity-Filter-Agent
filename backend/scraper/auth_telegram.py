import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
PHONE = os.environ.get("TELEGRAM_PHONE")

async def main():
    if not API_ID or not API_HASH or not PHONE:
        print("Error: TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE must be set in .env")
        return

    # The session file will be created in the same directory as this script.
    session_path = os.path.join(os.path.dirname(__file__), 'career_agent')
    print(f"Initializing TelegramClient with session: {session_path}.session")
    
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    # This will prompt for the OTP in standard input
    await client.start(phone=PHONE)
    
    print("\nAuthentication successful! 'career_agent.session' has been securely generated.")
    print("You can now safely run the FastAPI server, and it will pick up the session automatically.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
