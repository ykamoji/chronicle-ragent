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

    def get_history(self, session_id: str) -> list:
        col = mongo.get_sessions_collection()
        if col is None: return []
        doc = col.find_one({"session_id": session_id})
        if not doc:
            return []

        messages = doc.get("messages", [])
        return messages

    def add_message(self, session_id: str, role: str, content: str, is_hidden: bool = False):
        col = mongo.get_sessions_collection()
        if col is None: return
        doc = col.find_one({"session_id": session_id})
        if not doc:
            self.create_conversation_with_id(session_id)
        
        message_obj = {
            "role": role.lower(),
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "is_hidden": is_hidden
        }

        col.update_one(
            {"session_id": session_id},
            {"$push": {"messages": message_obj}}
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
            "messages": [],
            "summary": []
        }
        col.insert_one(doc)

    def delete_last_query_internals(self, session_id: str) -> int:
        """Removes the last incomplete query round from MongoDB.

        Walks backwards through messages and deletes everything after the most
        recent visible agent answer — i.e. the failed user query plus all
        hidden agent thoughts and system observations that followed it.

        Returns the number of messages removed.
        """
        col = mongo.get_sessions_collection()
        if col is None:
            return 0

        doc = col.find_one({"session_id": session_id})
        if not doc:
            return 0

        messages = doc.get("messages", [])
        if not messages:
            return 0

        # Walk backwards to find where the last visible agent answer ends.
        # Everything after that index (inclusive of the failed user query) is removed.
        cut_index = len(messages)  # default: remove nothing
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            # Stop as soon as we hit a visible agent reply — that's the last
            # successful exchange; we keep everything up to and including it.
            if not msg.get("is_hidden") and msg.get("role") == "agent":
                cut_index = i + 1
                break
            # If we reach the beginning without finding a visible agent reply,
            # remove from the first user message onwards.
            if i == 0:
                cut_index = 0

        removed_count = len(messages) - cut_index
        if removed_count == 0:
            return 0

        # Slice the list and persist
        trimmed = messages[:cut_index]
        col.update_one(
            {"session_id": session_id},
            {"$set": {"messages": trimmed}}
        )
        return removed_count        

# Global memory instance
memory = AgentMemory()
