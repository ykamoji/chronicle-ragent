import os
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB_NAME", "chronicle_rag")
        mongo_collection_name = os.getenv("MONGO_COLLECTION_NAME", "documents")

        if not mongo_uri:
            logger.warning("MONGO_URI is not set. MongoDB will not connect.")
            self.client = None
            self.db = None
            self.collection = None
            return
            
        try:
            self.client = MongoClient(mongo_uri)
            self.db: Database = self.client[mongo_db_name]
            self.collection: Collection = self.db[mongo_collection_name]
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self.collection = None

    def get_collection(self) -> Collection:
        return self.collection

# Singleton instance
mongo = MongoDBClient()
