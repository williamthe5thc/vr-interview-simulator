"""True while code runs on behalf of a WEB (browser) session. The websocket server sets it per turn; the LLM client reads it so that a web
session never falls back silently to the local model, and the log filter reads it so that web users' words are never written to the log."""
import contextvars

WEB = contextvars.ContextVar("web_session", default=False)
