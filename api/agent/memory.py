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
        }
        col.insert_one(doc)

    def delete_last_query_internals(self, session_id: str) -> int:
        """Removes the last incomplete query round from MongoDB."""
        col = mongo.get_sessions_collection()
        if col is None:
            return 0

        doc = col.find_one({"session_id": session_id})
        if not doc:
            return 0

        messages = doc.get("messages", [])
        if not messages:
            return 0

        total_input = len(messages)
        # Walk backwards to find where the last visible agent answer ends.
        cut_index = total_input  # default: remove nothing
        for i in range(total_input - 1, -1, -1):
            msg = messages[i]
            # Stop as soon as we hit a visible agent reply
            if not msg.get("is_hidden") and msg.get("role") == "agent":
                cut_index = i + 1
                import logging
                logging.getLogger(__name__).info(f"Cleanup: Found last visible agent reply at index {i}. Truncating after it.")
                break
            if i == 0:
                cut_index = 0
                import logging
                logging.getLogger(__name__).info("Cleanup: No visible agent reply found. Truncating from the beginning.")

        removed_count = total_input - cut_index
        if removed_count == 0:
            import logging
            logging.getLogger(__name__).info(f"Cleanup: session {session_id} is already clean (total={total_input}).")
            return 0

        # Slice the list and persist
        trimmed = messages[:cut_index]
        col.update_one(
            {"session_id": session_id},
            {"$set": {"messages": trimmed}}
        )
        import logging
        logging.getLogger(__name__).info(f"Cleanup: session {session_id} - removed {removed_count} messages. New total: {cut_index}.")
        return removed_count        

# Global memory instance
memory = AgentMemory()
