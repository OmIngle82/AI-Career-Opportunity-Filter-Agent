from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

# This will prompt you for your phone number and login code one last time
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n--- COPY THE STRING BELOW ---")
    print(client.session.save())
