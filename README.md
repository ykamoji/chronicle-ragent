# Chronicle Agentic RAG

A production-ready Agentic Retrieval-Augmented Generation (RAG) backend utilizing a ReAct engine.

Designed for ingesting text or PDF documents into a MongoDB Atlas Vector Store, extracting rich metadata via Google Gemini, and intelligently routing queries across multiple specialized search tools in real-time.

## Features
- **Agentic ReAct Architecture**: Engineered a multi-tool ReAct (Reasoning + Acting) loop allowing an autonomous AI agent to solve complex queries via semantic matching, keyword regex lookups, and metadata filters.
- **Automated Ingestion Pipeline**: Built an asynchronous ingestion service that chunks PDFs/text, extracts chapter/character metadata via LLMs, and computes vector embeddings prior to bulk MongoDB insertion.
- **Hybrid Search Engine**: Leveraged MongoDB Atlas capabilities to route questions through high-dimensional cosine similarity Vector Search alongside robust traditional keyword queries.
- **FastAPI Backend**: Architected a typed, high-performance API endpoint structure handling seamless stateful conversation tracking via an in-memory session manager.

## Prerequisites
- **Python 3.11+**
- **MongoDB Atlas Cluster**
- **Google Gemini API Key**

## Setup & Configuration

1. **Clone the project & use environment**
   ```bash
   conda create -n chronicle python=3.11 -y
   conda activate chronicle
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   # .env
   MONGO_URI="mongodb+srv://<user>:<pwd>@cluster.../?retryWrites=true&w=majority"
   MONGO_DB_NAME="chronicle"
   GEMINI_API_KEY="your_api_key_here"
   ```

3. **Configure MongoDB Atlas Vector Index**
   To enable the agent's `vector_search` tool, go to your Atlas UI -> **Atlas Search** -> **Create Search Index** -> **Atlas Vector Search (JSON)**.
   Name the index `vector_index` and use the following JSON configuration. (Google's `text-embedding-004` outputs 768 dimensions)