from dotenv import load_dotenv
import os
import sys

# Load env before importing notifications so Twilio gets the right vars
load_dotenv()

from notifications import send_whatsapp_alert

def main():
    print("Testing WhatsApp alert...")
    
    pros = ['Matches Next.js & Java stack', 'Located in Pune']
    pros_text = "\n".join(f"• {p}" for p in pros)
    
    send_whatsapp_alert(
        job_title="Full Stack Engineer",
        company="Test Tech Pune",
        score=90,
        link="https://example.com",
        pros=pros_text
    )

if __name__ == "__main__":
    main()
