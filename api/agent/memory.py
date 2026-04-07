from uuid import uuid4
from datetime import datetime

class AgentMemory:
    """Simple in-memory conversation store for the agent."""
    def __init__(self):
        self.conversations = {}

    def create_conversation(self) -> str:
        session_id = str(uuid4())
        self.conversations[session_id] = {
            "created_at": datetime.now().isoformat(),
            "history": []
        }
        return session_id

    def get_history(self, session_id: str) -> list[str]:
        if session_id not in self.conversations:
            return []
        return self.conversations[session_id]["history"]

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.conversations:
            self.create_conversation_with_id(session_id)
        self.conversations[session_id]["history"].append(f"{role}: {content}")
        
    def create_conversation_with_id(self, session_id: str):
        self.conversations[session_id] = {
            "created_at": datetime.now().isoformat(),
            "history": []
        }

# Global memory instance
memory = AgentMemory()
