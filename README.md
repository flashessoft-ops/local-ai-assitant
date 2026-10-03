# Local Chat

React on port 5173 → FastAPI on port 8000 → Ollama on port 11434, using `qwen3:1.7b`. Topics and messages are stored in `backend/chat.db` (SQLite).

## Setup (PowerShell)

Prerequisites: Python 3.11+, Node.js 20.19+ or 22.12+, and Ollama installed.

```powershell
ollama pull qwen3:1.7b
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
npm --prefix frontend install
```

Start Ollama with `ollama serve` if its desktop app is not already running. In a separate terminal, start the API from the project directory:

```powershell
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs.

After setup, double-click **Start Chat.cmd** to launch both servers in the background, then open http://127.0.0.1:5173. Double-click **Stop Chat.cmd** to stop them. Alternatively, run `./start.ps1` and `./stop.ps1` from PowerShell. Logs and tracked process IDs are in `.runtime`. Saved chats are preserved. The scripts start Ollama if needed and stop it only if they launched it; an already-running Ollama desktop service is left running. Wait for any reply before stopping, because stopping terminates active requests.

These scripts use Python and Node directly, so npm is not needed to start the installed app. A pnpm lockfile is included; pnpm users can install with `pnpm --dir frontend install` instead of npm.

Create conversations, switch between saved topics, and delete topics with their messages. The first message becomes the topic title. Enter sends; Shift+Enter inserts a line break. A failed generation preserves the draft and saves neither message, so it can be retried without duplicated history. One generation runs at a time. Requests time out after 180 seconds; the last 40 saved messages are provided as context. Replies are displayed as plain text.

Optional backend environment variables: `OLLAMA_MODEL`, `OLLAMA_URL`, and `CHAT_DB`. Restart the API after changing these. Use a single API worker because generation coordination is in-process. This app is for trusted local use and has no authentication; keep services bound to loopback. Downloads require internet access during setup; chat inference runs locally.

Build the frontend with `npm --prefix frontend run build`. The production build requires a server that proxies `/api` to FastAPI; the included Vite development server already provides this proxy.
