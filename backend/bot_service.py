import os
import sys
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAW_CHAT_ID = os.getenv("TELEGRAM_USER_CHAT_ID", "1220500210")

try:
    USER_CHAT_ID = int(RAW_CHAT_ID)
except (ValueError, TypeError):
    USER_CHAT_ID = RAW_CHAT_ID

def get_db():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

_bot_client: TelegramClient = None

def get_bot_client() -> TelegramClient:
    global _bot_client
    if _bot_client is None:
        bot_session = os.path.join(os.path.dirname(__file__), "scraper", "bot_agent")
        _bot_client = TelegramClient(bot_session, API_ID, API_HASH)
    return _bot_client

async def send_bot_alert_message(opportunity_dict: dict):
    client = get_bot_client()
    if not client.is_connected():
        await client.start(bot_token=BOT_TOKEN)

    title = opportunity_dict.get('title', 'Unknown Role')
    company = opportunity_dict.get('company', 'Unknown Company')
    category = opportunity_dict.get('category', 'Job')
    match_score = opportunity_dict.get('match_score', 0)
    source_name = opportunity_dict.get('source_name', 'Telegram')
    apply_url = opportunity_dict.get('apply_url') or opportunity_dict.get('source_url', '')
    opp_id = opportunity_dict.get('id')

    pros_list = opportunity_dict.get('pros', [])
    match_rationale = "\n".join(f"• {p}" for p in pros_list[:2]) if pros_list else "Strong profile alignment!"

    text = (
        f"🚀 **New High-Match Opportunity!**\n\n"
        f"💼 **Role:** {title}\n"
        f"🏢 **Company:** {company}\n"
        f"🏷️ **Category:** {category}\n"
        f"🎯 **Match Score:** {match_score}/100\n"
        f"📡 **Source:** {source_name}\n\n"
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

    btn_arg = buttons if buttons else None
    msg = await client.send_message(USER_CHAT_ID, text, buttons=btn_arg, parse_mode="md")
    print(f"[Telegram Bot] Interactive notification sent! Message ID: {msg.id}")
    return msg.id

async def start_bot_service():
    """
    Long-running background service that powers 2-way interactivity for the Telegram Bot:
    - Handles inline callback buttons (Save / Dismiss)
    - Responds to /start, /status, /recent commands
    """
    if not BOT_TOKEN or not API_ID or not API_HASH:
        print("[Telegram Bot] Bot credentials missing in .env. Service disabled.")
        return

    client = get_bot_client()
    try:
        await client.start(bot_token=BOT_TOKEN)
        bot_user = await client.get_me()
        print(f"[Telegram Bot] Interactive Bot Service started as @{bot_user.username} (ID: {bot_user.id})")

        @client.on(events.CallbackQuery)
        async def on_callback(event):
            try:
                data_bytes = event.data
                data = data_bytes.decode('utf-8') if isinstance(data_bytes, bytes) else str(data_bytes)
                db = get_db()

                if data.startswith("save:"):
                    opp_id = data.split("save:", 1)[1]
                    db.table('opportunities').update({'status': 'SAVED'}).eq('id', opp_id).execute()
                    await event.answer("Saved to your dashboard ⭐", alert=False)
                    
                    # Update buttons to reflect action
                    new_buttons = []
                    # Keep original apply url button if present
                    if event.message.buttons and len(event.message.buttons) > 1:
                        top_row = event.message.buttons[0]
                        new_buttons.append(top_row)
                    new_buttons.append([
                        Button.inline("✅ Saved", data=f"noop:{opp_id}"),
                        Button.inline("🗑️ Dismiss", data=f"dismiss:{opp_id}")
                    ])
                    try:
                        await event.edit(buttons=new_buttons)
                    except Exception:
                        pass

                elif data.startswith("dismiss:"):
                    opp_id = data.split("dismiss:", 1)[1]
                    db.table('opportunities').update({'status': 'DISMISSED'}).eq('id', opp_id).execute()
                    await event.answer("Opportunity archived 🗑️", alert=False)

                    new_buttons = []
                    if event.message.buttons and len(event.message.buttons) > 1:
                        top_row = event.message.buttons[0]
                        new_buttons.append(top_row)
                    new_buttons.append([
                        Button.inline("⭐ Restore", data=f"save:{opp_id}"),
                        Button.inline("🗄️ Archived", data=f"noop:{opp_id}")
                    ])
                    try:
                        await event.edit(buttons=new_buttons)
                    except Exception:
                        pass

                elif data.startswith("noop:"):
                    await event.answer("Already updated!", alert=False)

            except Exception as e:
                print(f"[Telegram Bot Callback Error] {e}")
                await event.answer("Failed to update status", alert=True)

        @client.on(events.NewMessage(pattern=r'^/start$'))
        async def on_start(event):
            welcome_text = (
                "👋 **Welcome to your AI Career Opportunity Bot!**\n\n"
                "I actively monitor tech communities and career boards, scoring roles with Gemini against your resume and profile.\n\n"
                "**Available Commands:**\n"
                "• `/recent` — Fetch top 3 latest high-match opportunities\n"
                "• `/exams` — View upcoming tracked exams & deadlines (GATE, TCS NQT, PSU)\n"
                "• `/status` — View your live ATS pipeline summary\n"
                "• `/help` — How to use this bot"
            )
            await event.respond(welcome_text, parse_mode="md")

        @client.on(events.NewMessage(pattern=r'^/help$'))
        async def on_help(event):
            help_text = (
                "💡 **How to use AI Career Filter Bot:**\n\n"
                "1. **Real-Time Alerts:** When high-match jobs (score ≥ 75) are found, you'll get instant alerts here.\n"
                "2. **Interactive Triage:** Tap **⭐ Save** to bookmark an opportunity for later, or **🗑️ Dismiss** to archive it.\n"
                "3. **Sync with Dashboard:** All actions you take here immediately sync to your web dashboard!\n"
                "4. **Commands:** Run `/recent` to inspect your latest leads or `/status` for pipeline statistics."
            )
            await event.respond(help_text, parse_mode="md")

        @client.on(events.NewMessage(pattern=r'^/status$'))
        async def on_status(event):
            try:
                db = get_db()
                res = db.table('opportunities').select('status').execute()
                all_ops = res.data or []
                
                total = len(all_ops)
                inbox = sum(1 for o in all_ops if (o.get('status') or 'INBOX') == 'INBOX')
                saved = sum(1 for o in all_ops if o.get('status') == 'SAVED')
                applied = sum(1 for o in all_ops if o.get('status') == 'APPLIED')
                dismissed = sum(1 for o in all_ops if o.get('status') == 'DISMISSED')

                status_text = (
                    "📊 **Your Career Pipeline Status:**\n\n"
                    f"📥 **Inbox:** {inbox} new leads\n"
                    f"⭐ **Saved:** {saved} opportunities\n"
                    f"🎯 **Applied:** {applied} submissions\n"
                    f"🗄️ **Archived:** {dismissed} leads\n"
                    f"📈 **Total Tracked:** {total} opportunities\n\n"
                    f"💡 *Tip: Open your dashboard to generate custom AI cold outreach pitches!*"
                )
                await event.respond(status_text, parse_mode="md")
            except Exception as e:
                await event.respond(f"⚠️ Failed to retrieve pipeline status: {e}")

        @client.on(events.NewMessage(pattern=r'^/recent$'))
        async def on_recent(event):
            try:
                db = get_db()
                res = db.table('opportunities').select('*').order('created_at', desc=True).limit(20).execute()
                items = res.data or []
                
                # Filter top 3 non-dismissed items with highest match scores
                active_items = [o for o in items if o.get('status') != 'DISMISSED']
                top_items = sorted(active_items, key=lambda x: x.get('match_score', 0), reverse=True)[:3]

                if not top_items:
                    await event.respond("No recent opportunities found in your inbox.")
                    return

                await event.respond(f"🔍 **Top {len(top_items)} Recent Opportunities:**\n")
                for opp in top_items:
                    title = opp.get('title', 'Unknown Role')
                    company = opp.get('company', 'Unknown Company')
                    match_score = opp.get('match_score', 0)
                    apply_url = opp.get('apply_url') or opp.get('source_url', '')
                    opp_id = opp.get('id')

                    buttons = []
                    if apply_url and (apply_url.startswith("http://") or apply_url.startswith("https://")):
                        buttons.append([Button.url("👉 Apply Now", apply_url)])
                    if opp_id:
                        buttons.append([
                            Button.inline("⭐ Save", data=f"save:{opp_id}"),
                            Button.inline("🗑️ Dismiss", data=f"dismiss:{opp_id}")
                        ])

                    card_text = (
                        f"💼 **{title}**\n"
                        f"🏢 {company} | 🎯 Match: **{match_score}/100**\n"
                    )
                    await client.send_message(event.chat_id, card_text, buttons=buttons or None, parse_mode="md")

            except Exception as e:
                await event.respond(f"⚠️ Failed to fetch recent opportunities: {e}")

        @client.on(events.NewMessage(pattern=r'^/exams$'))
        async def on_exams(event):
            try:
                db = get_db()
                res = db.table('opportunities').select('*').eq('category', 'Exam').order('created_at', desc=True).limit(15).execute()
                items = [o for o in (res.data or []) if o.get('status') != 'DISMISSED']

                if not items:
                    await event.respond("No active Exam notifications found right now. Exam Radar runs automatically!")
                    return

                # Sort by application_deadline ascending when present, else newest first
                items.sort(key=lambda x: (x.get('application_deadline') is None, x.get('application_deadline') or ''))
                top_exams = items[:5]
                await event.respond(f"🎓 **Upcoming Tracked Exams & Drives ({len(top_exams)}):**\n")

                for opp in top_exams:
                    title = opp.get('title', 'Exam Notification')
                    company = opp.get('company', 'Official Portal')
                    deadline = str(opp.get('application_deadline') or '')[:10]
                    exam_dt = str(opp.get('exam_date') or '')[:10]
                    apply_url = opp.get('apply_url') or opp.get('source_url', '')
                    opp_id = opp.get('id')

                    buttons = []
                    if apply_url and apply_url.startswith(('http://', 'https://')):
                        buttons.append([Button.url("👉 Official Portal", apply_url)])
                    if opp_id:
                        buttons.append([
                            Button.inline("⭐ Save", data=f"save:{opp_id}"),
                            Button.inline("🗑️ Dismiss", data=f"dismiss:{opp_id}")
                        ])

                    lines = [f"📝 **{title}**", f"🏛️ {company} | 🎯 Match: **{opp.get('match_score', 0)}/100**"]
                    if deadline:
                        lines.append(f"⏳ Last Date: **{deadline}**")
                    if exam_dt:
                        lines.append(f"📅 Exam Date: **{exam_dt}**")

                    await client.send_message(event.chat_id, "\n".join(lines), buttons=buttons or None, parse_mode="md")
            except Exception as e:
                await event.respond(f"⚠️ Failed to fetch exams: {e}")

        await client.run_until_disconnected()
    except Exception as e:
        print(f"[Telegram Bot Service Error] {e}")

if __name__ == "__main__":
    asyncio.run(start_bot_service())
