import os
from twilio.rest import Client
import traceback
from dotenv import load_dotenv

load_dotenv()

def send_whatsapp_alert(opportunity_dict: dict):
    """
    Sends a WhatsApp message using the Twilio Sandbox.
    """
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_raw = os.getenv("TWILIO_WHATSAPP_SENDER", "whatsapp:+14155238886")
        to_raw = os.getenv("USER_WHATSAPP_NUMBER")
        
        if not account_sid or not auth_token or not to_raw:
            print("[WhatsApp Warning] Missing Twilio credentials or USER_WHATSAPP_NUMBER in .env. Skipping alert.")
            return None
            
        to_whatsapp_number = to_raw if to_raw.startswith('whatsapp:') else f'whatsapp:{to_raw}'
        from_whatsapp_number = from_raw if from_raw.startswith('whatsapp:') else f'whatsapp:{from_raw}'
        
        client = Client(account_sid, auth_token)
        
        title = opportunity_dict.get('title', 'Unknown Role')
        company = opportunity_dict.get('company', 'Unknown Company')
        category = opportunity_dict.get('category', 'Other')
        match_score = opportunity_dict.get('match_score', 0)
        
        # Format the pros into a rationale list
        pros_list = opportunity_dict.get('pros', [])
        match_rationale = "\n".join(f"• {p}" for p in pros_list[:2]) if pros_list else "Great match based on your profile!"
        
        apply_url = opportunity_dict.get('apply_url') or opportunity_dict.get('source_url', 'No link provided')
        
        message_body = f"🚀 *New High-Match Opportunity!*\n\n" \
                       f"*Role:* {title}\n" \
                       f"*Company:* {company}\n" \
                       f"*Category:* {category}\n" \
                       f"*Match Score:* {match_score}/100\n\n" \
                       f"*Why it fits:*\n{match_rationale}\n\n" \
                       f"🔗 *Apply Here:* {apply_url}"
                       
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp_number if from_whatsapp_number.startswith('whatsapp:') else f'whatsapp:{from_whatsapp_number}',
            to=to_whatsapp_number
        )
        print(f"[WhatsApp] Dispatched message SID: {message.sid}")
        
    except Exception as e:
        print(f"[WhatsApp Error] Failed to send: {str(e)}")
        traceback.print_exc()
