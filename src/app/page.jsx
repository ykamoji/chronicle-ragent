"use client";
import { useState, useRef, useEffect } from "react";
import "./globals.css";

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const chatWindowRef = useRef(null);

  // Automatically routes through next.config.mjs rewrites to the FastAPI server on 8000
  const API_URL = "";

  // Auto-scroll chat
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;

    const userQuery = query.trim();
    setQuery("");
    setMessages((prev) => [...prev, { role: "user", content: userQuery }]);
    setIsLoading(true);

    try {
      const payload = { query: userQuery };
      if (sessionId) payload.session_id = sessionId;

      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("API request failed");

      const data = await res.json();
      if (!sessionId) setSessionId(data.session_id);

      setMessages((prev) => [
        ...prev,
        { role: "agent", content: data.answer },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Error connecting to backend API." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus("Uploading...");
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) {
      formData.append("session_id", sessionId);
    }

    try {
      const res = await fetch(`${API_URL}/ingest`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      
      const data = await res.json();
      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      setUploadStatus(`Ingesting ${file.name}...`);
    } catch (err) {
      console.error(err);
      setUploadStatus("Failed to upload.");
    }
  };

  return (
    <div className="dashboard-layout">
      {/* Main Chat Interface */}
      <main className="chat-container glass-panel">
        <div style={{ padding: "24px", borderBottom: "1px solid var(--panel-glass-border)" }}>
          <h1>Chronicle <span style={{ color: "var(--accent-cyan)" }}>Agentic ORB</span></h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Real-time RAG inference powered by ReAct
          </p>
        </div>

        <div className="chat-window" ref={chatWindowRef}>
          {messages.length === 0 && (
            <div style={{ margin: "auto", textAlign: "center", color: "var(--text-secondary)" }}>
              <h2>Start a conversation</h2>
              <p>Ask about characters, summaries, or specific text segments.</p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div key={index} className={`chat-bubble ${msg.role}`}>
              {msg.content.split('\n').map((line, i) => (
                <span key={i}>
                  {line}
                  <br />
                </span>
              ))}
            </div>
          ))}

          {isLoading && (
            <div className="chat-bubble agent">
              <div className="loader"></div> Thinking...
            </div>
          )}
        </div>

        <form className="chat-input-area" onSubmit={handleSend}>
          <input
            type="text"
            placeholder="Ask the agent anything..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !query.trim()}>
            Send Message
          </button>
        </form>
      </main>

      {/* Side Ingestion Panel */}
      <aside className="ingestion-panel glass-panel">
        <h2>Document Hub</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Upload PDF or text files to build the agent's knowledge base.
        </p>

        <div
          className="file-drop-zone"
          onClick={() => document.getElementById('file-upload').click()}
        >
          <input
            type="file"
            id="file-upload"
            style={{ display: "none" }}
            accept=".pdf,.txt"
            onChange={handleFileUpload}
          />
          <p>📄 Click to Upload Document</p>
          <span style={{ fontSize: "0.8rem" }}>Supports: PDF, TXT</span>
        </div>

        {uploadStatus && (
          <div style={{ padding: "12px", background: "rgba(0,210,255,0.1)", borderRadius: "8px", fontSize: "0.9rem" }}>
            {uploadStatus}
          </div>
        )}
      </aside>
    </div>
  );
}
