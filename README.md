# AI Career Opportunity Filter Agent

An end-to-end, autonomous AI pipeline designed to aggregate, score, and filter career opportunities (Jobs, Internships, Exams) based on a user's highly specific preferences, technical background, and schedule constraints.

## 🚀 Live Architecture

The platform is designed to run statelessly in the cloud, utilizing an event-driven architecture and a robust, dual-LLM fallback pipeline.

### Frontend
- **Framework**: Next.js (React) + Tailwind CSS
- **Deployment**: Vercel
- **Features**: Interactive dashboard for opportunity management, real-time profile configuration, and AI-driven resume synthesis.

### Backend
- **Framework**: FastAPI + Docker
- **Deployment**: Render (or any Docker-compatible cloud provider)
- **Ingestion Mechanisms**:
  - **Playwright Crawler**: Headless Chromium instance running inside the Docker container to deep-crawl public job boards and forums.
  - **Telegram Daemon**: Async listener built on Telethon capturing real-time updates from high-velocity career channels.

### Data & Authentication
- **Database**: Supabase (PostgreSQL) for storing user profiles, active schedules, and structured opportunity evaluations.
- **Stateless Auth**: Telethon `StringSession` allows the Telegram daemon to authenticate dynamically in cloud environments without relying on persistent local `.session` SQLite files.

### AI Pipeline (Dual-LLM Resiliency)
- **Primary Agent**: Google Gemini 3.6 Flash (via LangChain).
- **Fallback Agent**: Groq Llama 3.1 70B (Versatile).
- **Mechanism**: If the primary agent hits a rate limit (429) or fails, the pipeline intercepts the error, truncates the context window appropriately, and dynamically queries the Groq API for available Llama 70B models, ensuring zero downtime during massive scraping tasks.

### Alerts & Notifications
- **Engine**: Twilio WhatsApp API
- **Logic**: Opportunities that score exceptionally high (`>= 85/100`) against the user's strict AI filtering directive trigger an immediate, summarized WhatsApp alert directly to the user's phone.

## 🛠️ Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase Project (URL & Key)
- Gemini API Key
- Groq API Key (Optional, for fallback)
- Telegram API ID & Hash
- Twilio Credentials (Optional)

### Running the Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
playwright install --with-deps chromium

# Authenticate Telegram (Generates TELEGRAM_SESSION_STRING)
python scripts/loginScript.py 

uvicorn main:app --reload
```

### Running the Frontend
```bash
cd desktop-web
npm install
npm run dev
```

## 🔒 Security Notes
Ensure that your `.env` file is never committed. When deploying to the cloud, use environment variables to inject sensitive credentials, specifically `TELEGRAM_SESSION_STRING` for stateless authentication.
