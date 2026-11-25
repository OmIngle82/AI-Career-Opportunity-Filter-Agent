import os
import asyncio
from typing import Optional
from telethon import TelegramClient, Button
from telethon.sessions import MemorySession
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def _resolve_chat_id(explicit_chat_id: Optional[str] = None):
    raw_chat_id = explicit_chat_id or os.getenv("TELEGRAM_USER_CHAT_ID", "1220500210")
    try:
        return int(raw_chat_id)
    except (ValueError, TypeError):
        return raw_chat_id


def _format_telegram_opportunity(opportunity_dict: dict) -> tuple[str, list | None]:
    title = opportunity_dict.get('title', 'Unknown Role')
    company = opportunity_dict.get('company', 'Unknown Company')
    category = opportunity_dict.get('category', 'Job')
    match_score = opportunity_dict.get('match_score', 0)
    source_name = opportunity_dict.get('source_name', 'Career Radar')
    apply_url = opportunity_dict.get('apply_url') or opportunity_dict.get('source_url', '')
    opp_id = opportunity_dict.get('id')
    stipend = opportunity_dict.get('stipend_or_ctc')
    deadline = opportunity_dict.get('application_deadline')
    is_official = opportunity_dict.get('is_official_source', False)

    pros_list = opportunity_dict.get('pros') or []
    match_rationale = "\n".join(f"• {p}" for p in pros_list[:2]) if pros_list else "Strong profile alignment!"

    portal_badge = "✅ Official Portal" if is_official else "🔗 Aggregator / Post"
    meta_lines = []
    if stipend:
        meta_lines.append(f"💰 **Comp/Stipend:** {stipend}")
    if deadline:
        meta_lines.append(f"⏳ **Deadline:** {str(deadline)[:10]}")
    meta_block = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

    text = (
        f"🚀 **New Opportunity Alert!**\n\n"
        f"💼 **Role:** {title}\n"
        f"🏢 **Company:** {company}\n"
        f"🏷️ **Category:** {category} ({portal_badge})\n"
        f"🎯 **Match Score:** {match_score}/100\n"
        f"📡 **Source:** {source_name}"
        f"{meta_block}\n\n"
        f"💡 **Why it fits:**\n"
        f"{match_rationale}\n"
    )

    buttons = []
    if apply_url and (apply_url.startswith("http://") or apply_url.startswith("https://")):
        buttons.append([Button.url("👉 Apply Now", apply_url)])

    if opp_id:
        buttons.append([
            Button.inline("⭐ Save", data=f"save:{opp_id}"),
            Button.inline("🗑️ Dismiss", data=f"dismiss:{opp_id}")
        ])

    return text, (buttons if buttons else None)


async def async_send_telegram_bot_alert(opportunity_dict: dict, chat_id: Optional[str] = None):
    """Sends an interactive Telegram alert via MTProto MemorySession (non-locking)."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not bot_token or not api_id or not api_hash:
        print("[Telegram Bot] Credentials missing in .env. Skipping alert.")
        return None

    target_chat = _resolve_chat_id(chat_id or opportunity_dict.get('telegram_chat_id'))
    client = TelegramClient(MemorySession(), api_id, api_hash)

    try:
        await client.start(bot_token=bot_token)
        text, buttons = _format_telegram_opportunity(opportunity_dict)
        msg = await client.send_message(target_chat, text, buttons=buttons, parse_mode="md")
        print(f"[Telegram Bot] Alert sent via MTProto! Message ID: {msg.id} (Opp ID: {opportunity_dict.get('id')})")
        return msg.id
    except Exception as e:
        print(f"[Telegram Bot Error] Failed to send alert: {e}")
        return None
    finally:
        await client.disconnect()


async def async_send_telegram_text(message_text: str, chat_id: Optional[str] = None):
    """Sends a formatted Markdown notification (used for deadline reminders & digests)."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not bot_token or not api_id or not api_hash:
        return None

    target_chat = _resolve_chat_id(chat_id)
    client = TelegramClient(MemorySession(), api_id, api_hash)
    try:
        await client.start(bot_token=bot_token)
        msg = await client.send_message(target_chat, message_text, parse_mode="md")
        return msg.id
    except Exception as e:
        print(f"[Telegram Bot Error] Failed to send text alert: {e}")
        return None
    finally:
        await client.disconnect()


def send_telegram_bot_alert(opportunity_dict: dict, chat_id: Optional[str] = None):
    """Synchronous wrapper for sending Telegram alerts from thread/sync contexts."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return loop.create_task(async_send_telegram_bot_alert(opportunity_dict, chat_id=chat_id))
        return asyncio.run(async_send_telegram_bot_alert(opportunity_dict, chat_id=chat_id))
    except Exception as e:
        print(f"[Telegram Bot Error] Failed to schedule alert: {e}")
        return None


def send_whatsapp_alert(opportunity_dict: dict):
    """
    Sends high-match (>= 85) alert via Twilio WhatsApp Sandbox (best-effort).
    Completely decoupled from Telegram Bot alerts.
    """
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_raw = os.getenv("TWILIO_WHATSAPP_SENDER", "whatsapp:+14155238886")
        to_raw = os.getenv("USER_WHATSAPP_NUMBER")

        if not account_sid or not auth_token or not to_raw:
            return None

        to_whatsapp_number = to_raw if to_raw.startswith('whatsapp:') else f'whatsapp:{to_raw}'
        from_whatsapp_number = from_raw if from_raw.startswith('whatsapp:') else f'whatsapp:{from_raw}'

        client = Client(account_sid, auth_token)

        title = opportunity_dict.get('title', 'Unknown Role')
        company = opportunity_dict.get('company', 'Unknown Company')
        category = opportunity_dict.get('category', 'Other')
        match_score = opportunity_dict.get('match_score', 0)

        pros_list = opportunity_dict.get('pros') or []
        match_rationale = "\n".join(f"• {p}" for p in pros_list[:2]) if pros_list else "Great match based on your profile!"
        apply_url = opportunity_dict.get('apply_url') or opportunity_dict.get('source_url', 'No link provided')

        message_body = (
            f"🚀 *New High-Match Opportunity!*\n\n"
            f"*Role:* {title}\n"
            f"*Company:* {company}\n"
            f"*Category:* {category}\n"
            f"*Match Score:* {match_score}/100\n\n"
            f"*Why it fits:*\n{match_rationale}\n\n"
            f"👉 *Apply:* {apply_url}"
        )

        message = client.messages.create(
            from_=from_whatsapp_number,
            body=message_body,
            to=to_whatsapp_number
        )
        print(f"[WhatsApp] Alert sent! SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"[WhatsApp Error] Best-effort WhatsApp send failed (may need 72h sandbox rejoin): {e}")
        return None


async def async_notify_new_opportunity(db, opportunity_record: dict, profile: dict):
    """
    Reliable multi-tenant dispatcher:
    1. Telegram Bot: fires for EVERY opportunity >= user.min_alert_score (default 60)
       and updates telegram_notified = TRUE upon confirmed delivery.
    2. WhatsApp: fires independently for >= 85 high-match alerts.
    """
    try:
        score_val = int(float(opportunity_record.get('match_score', 0)))
    except (ValueError, TypeError):
        score_val = 0

    min_alert_score = profile.get('min_alert_score')
    if min_alert_score is None:
        min_alert_score = 60

    chat_id = profile.get('telegram_chat_id') or os.getenv("TELEGRAM_USER_CHAT_ID")
    opp_id = opportunity_record.get('id')

    if score_val >= min_alert_score:
        msg_id = await async_send_telegram_bot_alert(opportunity_record, chat_id=chat_id)
        if msg_id and opp_id and db is not None:
            try:
                db.table('opportunities').update({'telegram_notified': True}).eq('id', opp_id).execute()
            except Exception as e:
                print(f"[Outbox Warning] Could not mark telegram_notified=True for {opp_id}: {e}")

    if score_val >= 85:
        await asyncio.to_thread(send_whatsapp_alert, opportunity_record)


def notify_new_opportunity_sync(db, opportunity_record: dict, profile: dict):
    """Synchronous helper for thread workers (e.g. telegram_listener.process_telegram_message)."""
    asyncio.run(async_notify_new_opportunity(db, opportunity_record, profile))
