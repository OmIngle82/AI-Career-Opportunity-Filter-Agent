import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def test_bot():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_USER_CHAT_ID", "1220500210")

    if not bot_token:
        print("\n" + "="*60)
        print("❌ TELEGRAM_BOT_TOKEN is not set in backend/.env!")
        print("="*60)
        print("\nFollow these 2 quick steps (takes ~30 seconds):")
        print("1. Open Telegram on your phone and search for: @BotFather")
        print("2. Send: /newbot")
        print("   - Enter a display name (e.g. 'Om Career Alerts')")
        print("   - Enter a username ending in 'bot' (e.g. 'OmCareerAlerts_bot')")
        print("3. BotFather will give you a token like:")
        print("   782910384:AAH1234abcd5678efgh")
        print("\n4. Add it to backend/.env:")
        print("   TELEGRAM_BOT_TOKEN=<your-token-here>")
        print(f"   TELEGRAM_USER_CHAT_ID={chat_id}")
        print("\n5. Open your newly created bot in Telegram and tap 'START'.")
        print("6. Run this test script again!")
        print("="*60 + "\n")
        return False

    print(f"\n[1/3] Testing Telegram Bot connection with token: {bot_token[:10]}...")
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/getMe")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                bot_info = data.get("result", {})
                print(f"  ✓ Connected to bot: @{bot_info.get('username')} ({bot_info.get('first_name')})")
            else:
                print(f"  ❌ Invalid token response: {data}")
                return False
    except Exception as e:
        print(f"  ❌ Failed to reach Telegram Bot API: {e}")
        return False

    print(f"\n[2/3] Preparing test high-match job alert for Chat ID: {chat_id}...")
    sample_job = {
        "title": "Machine Learning Engineer (Junior / Fresher)",
        "company": "Google",
        "category": "Job",
        "match_score": 96,
        "source_name": "OffCampusJobs4u",
        "apply_url": "https://careers.google.com",
        "pros": [
            "Strong match with Python, Scikit-learn, and NLP skillset.",
            "Pune / Mumbai location aligns with preferred zones."
        ]
    }

    print("\n[3/3] Sending test alert...")
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from notifier import send_telegram_bot_alert

    res = send_telegram_bot_alert(sample_job)
    if res:
        print(f"\n🎉 SUCCESS! Test notification sent to your phone (Message ID: {res}).")
        print("Check your Telegram app to see the rich alert with the 'Apply Now' button!\n")
        return True
    else:
        print("\n❌ Failed to dispatch message.")
        print("Make sure you opened your bot in Telegram and tapped 'START' before testing.\n")
        return False

if __name__ == "__main__":
    test_bot()
