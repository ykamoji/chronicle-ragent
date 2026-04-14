from uuid import uuid4
from datetime import datetime, timezone
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
        col = mongo.get_messages_collection()
        if col is None: return []
        
        cursor = col.find({"session_id": session_id}, {"_id": 0}).sort("timestamp", 1)
        return list(cursor)

    def add_message(self, session_id: str, role: str, content: str, is_hidden: bool = False, model_name: str = None, total_time: float = None):
        col = mongo.get_messages_collection()
        if col is None: return
        
        # Ensure session exists (metadata)
        sess_col = mongo.get_sessions_collection()
        if sess_col is not None and not sess_col.find_one({"session_id": session_id}):
            self.create_conversation_with_id(session_id)
        
        message_obj = {
            "session_id": session_id,
            "role": role.lower(),
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_hidden": is_hidden
        }
        
        if model_name:
            message_obj["model_name"] = model_name
        if total_time is not None:
            message_obj["total_time"] = round(total_time, 2)

        col.insert_one(message_obj)
        
    def create_conversation_with_id(self, session_id: str):
        col = mongo.get_sessions_collection()
        if col is None: return
        
        # Don't recreate if exists
        if col.find_one({"session_id": session_id}):
            return
            
        doc = {
            "session_id": session_id,
            "upload_time": datetime.now(timezone.utc).isoformat(),
        }
        col.insert_one(doc)

    def set_chat_name(self, session_id: str, agent_answer: str) -> str | None:
        """Generates a short chat title from the first agent answer and stores it in the session document.

        Only sets the name once — if a chat_name already exists it is left unchanged.
        Uses a minimal, non-thinking Gemini call to keep latency low.
        """
        col = mongo.get_sessions_collection()
        if col is None:
            return None

        # Only name sessions that don't have one yet
        doc = col.find_one({"session_id": session_id}, {"chat_name": 1})
        if not doc or doc.get("chat_name"):
            return None

        try:
            import os
            from google import genai
            from google.genai import types as gtypes
            from api.config.settings import app_settings

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return None

            client = genai.Client(api_key=api_key)
            prompt = (
                f"Generate a concise chat title of 4-6 words that captures the main topic of the content."
                f"Output ONLY the title — no punctuation, no quotes.\n\n"
                f"Content: {agent_answer}"
            )
            response = client.models.generate_content(
                model=app_settings.get_model(),
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=20
                )
            )
            chat_name = response.text.strip().strip('"').strip("'")[:80]  # trim safety cap
            col.update_one(
                {"session_id": session_id},
                {"$set": {"chat_name": chat_name}}
            )
            import logging
            logging.getLogger(__name__).info(f"Chat name set for session {session_id}: '{chat_name}'")
            return chat_name
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to generate chat name for session {session_id}: {e}")
            return None

    def delete_last_query_internals(self, session_id: str) -> int:
        """Removes the last incomplete query round from MongoDB."""
        col = mongo.get_messages_collection()
        if col is None:
            return 0

        # Find all messages for the session, chronological order
        messages = list(col.find({"session_id": session_id}).sort("timestamp", 1))
        
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

        # Gather the ObjectIds of the messages to delete
        ids_to_delete = [msg["_id"] for msg in messages[cut_index:]]
        
        result = col.delete_many({"_id": {"$in": ids_to_delete}})
        
        import logging
        logging.getLogger(__name__).info(f"Cleanup: session {session_id} - removed {result.deleted_count} messages. New total: {cut_index}.")
        return result.deleted_count

    def log_query_analytics(self, session_id: str, query: str, metrics: list):
        """Flushes a list of tool metrics to MongoDB analytics collection."""
        if not metrics:
            return
            
        col = mongo.get_analytics_collection()
        if col is None:
            return
            
        timestamp = datetime.now(timezone.utc).isoformat()
        docs_to_insert = []
        for m in metrics:
            doc = {
                "session_id": session_id,
                "query": query,
                "timestamp": timestamp,
                **m
            }
            docs_to_insert.append(doc)
            
        if docs_to_insert:
            col.insert_many(docs_to_insert)

# Global memory instance
memory = AgentMemory()
