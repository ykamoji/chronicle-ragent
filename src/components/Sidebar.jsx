"use client";
import { useState, useEffect } from "react";
import { useSession } from "../context/SessionContext";

const API_URL = "";

export default function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [sessionList, setSessionList] = useState([]);
  const { sessionId, loadSession, startNewChat } = useSession();

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessionList(data);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // Re-fetch session list whenever the active session changes (e.g. after upload creates one)
  useEffect(() => {
    fetchSessions();
  }, [sessionId]);

  return (
    <aside className={`sidebar-panel glass-panel ${isCollapsed ? "collapsed" : ""}`}>
      <div className="sidebar-header" style={{ display: "flex", justifyContent: isCollapsed ? "center" : "flex-end", marginBottom: "8px" }}>
        <button
          className="icon-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          style={{ padding: "8px 12px", background: "transparent", border: "1px solid var(--panel-glass-border)", borderRadius: "8px", color: "var(--text-primary)" }}
        >
          {isCollapsed ? "➡" : "⬅"}
        </button>
      </div>
      <button className="new-chat-btn" onClick={startNewChat} style={{ padding: isCollapsed ? "10px" : "10px 24px" }}>
        {isCollapsed ? "+" : "+ New Chat"}
      </button>

      {!isCollapsed && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px" }}>
          {sessionList.map((session) => (
            <div
              key={session.session_id}
              onClick={() => loadSession(session.session_id)}
              className={`sidebar-item ${sessionId === session.session_id ? "active" : ""}`}
            >
              Session - {new Date(session.upload_time).toLocaleDateString()}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
