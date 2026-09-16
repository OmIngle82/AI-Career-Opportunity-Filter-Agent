import os
import httpx
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

# These must be configured in .env for actual usage
API_ID = os.environ.get("TELEGRAM_API_ID", "123456")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "mock_hash")
PHONE = os.environ.get("TELEGRAM_PHONE", "+1234567890")

# Dummy channel for now, can be replaced by actual channel username or ID
CHANNEL_TO_LISTEN = 'dummy_career_channel'
EVALUATE_URL = "http://localhost:8000/evaluate"

# Using a session name 'scraper_session'
client = TelegramClient('scraper_session', API_ID, API_HASH)

@client.on(events.NewMessage(chats=CHANNEL_TO_LISTEN))
async def handler(event):
    message_text = event.message.message
    print(f"Received new message from {CHANNEL_TO_LISTEN}:\n{message_text}")
    
    payload = {
        "raw_text": message_text,
        "source_url": f"https://t.me/{CHANNEL_TO_LISTEN}/{event.message.id}",
        "source_name": f"Telegram: {CHANNEL_TO_LISTEN}",
        "source_tier": "TIER_1_TRUSTED"
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(EVALUATE_URL, json=payload, timeout=30.0)
            
            if response.status_code == 200:
                print("Successfully sent to evaluation pipeline.")
                print(response.json())
            else:
                print(f"Failed to evaluate. Status: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error communicating with backend API: {e}")

async def main():
    print(f"Starting Telegram Listener for channel: {CHANNEL_TO_LISTEN}")
    print("Note: If running for the first time, Telegram will ask for your phone number and login code.")
    # In a real environment, uncomment this to actually log in.
    # await client.start(phone=PHONE)
    print("Listening for messages... (Mocked: script initialized successfully)")
    # await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
