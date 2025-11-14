class SessionService:
    def __init__(self):
        self.sessions = {}

    def get(self, session_id: str):
        return self.sessions.setdefault(session_id, [])

    def set(self, session_id: str, history):
        self.sessions[session_id] = history

    def list(self):
        return [{"session_id": sid, "message_count": len(hist)} for sid, hist in self.sessions.items()]
