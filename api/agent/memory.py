from uuid import uuid4
from datetime import datetime
from api.db.mongo import mongo

class AgentMemory:
    """MongoDB backed conversation store for the agent."""
    def __init__(self):
        pass

    def create_conversation(self) -> str:
        session_id = str(uuid4())
        self.create_conversation_with_id(session_id)
        return session_id

    def get_history(self, session_id: str) -> list[str]:
        col = mongo.get_sessions_collection()
        if col is None: return []
        doc = col.find_one({"session_id": session_id})
        if not doc:
            return []
        return doc.get("chat_logs", [])

    def add_message(self, session_id: str, role: str, content: str):
        col = mongo.get_sessions_collection()
        if col is None: return
        doc = col.find_one({"session_id": session_id})
        if not doc:
            self.create_conversation_with_id(session_id)
        
        col.update_one(
            {"session_id": session_id},
            {"$push": {"chat_logs": f"{role}: {content}"}}
        )
        
    def create_conversation_with_id(self, session_id: str):
        col = mongo.get_sessions_collection()
        if col is None: return
        
        # Don't recreate if exists
        if col.find_one({"session_id": session_id}):
            return
            
        doc = {
            "session_id": session_id,
            "upload_time": datetime.now().isoformat(),
            "chat_logs": [],
            "summary": []
        }
        col.insert_one(doc)

# Global memory instance
memory = AgentMemory()
