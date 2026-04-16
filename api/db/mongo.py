import os
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB_NAME")

        if not mongo_uri:
            logger.warning("MONGO_URI is not set. MongoDB will not connect.")
            self.client = None
            self.db = None
            self.vector = None
            self.sessions = None
            self.messages = None
            self.analytics = None
            self.uploads = None
            return
            
        try:
            self.client = MongoClient(
                mongo_uri, 
                maxPoolSize=50,
                minPoolSize=5,
                serverSelectionTimeoutMS=30000
            )
            self.db: Database = self.client[mongo_db_name]
            self.vector: Collection = self.db['vector']
            self.sessions: Collection = self.db["sessions"]
            self.messages: Collection = self.db["messages"]
            self.analytics: Collection = self.db["analytics"]
            self.uploads: Collection = self.db["uploads"]

            try:
                self.db.command("ping")
            except Exception as e:
                raise RuntimeError(f"MongoDB connection failed: {e}")
                
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self.vector = None
            self.sessions = None
            self.messages = None
            self.analytics = None
            self.uploads = None

    def get_vector_collection(self) -> Collection:
        return self.vector

    def get_sessions_collection(self) -> Collection:
        return self.sessions

    def get_messages_collection(self) -> Collection:
        return self.messages

    def get_analytics_collection(self) -> Collection:
        return self.analytics

    def get_uploads_collection(self) -> Collection:
        return self.uploads

# Singleton instance
mongo = MongoDBClient()