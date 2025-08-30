# Guide For Coding AI Assistant — Execution Tasks
1) Backend FastAPI + /ws (JSON {event,data}) with stub handlers that let UI stubs work.
2) Claude-only provider (fail-fast); prompt loader from llm/prompts (hard-fail if missing).
3) Outlook Graph adapter skeleton.
4) Flat job queue and bg:job:status.
5) Context interviews: interview:start/answer/dismiss and push interview:questions.
6) Data models (SQLite via SQLAlchemy), minimal to get UI moving.
7) Electron connects to ws://127.0.0.1:8788/ws.
8) Replace mocks incrementally with Claude calls.
