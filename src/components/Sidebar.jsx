"use client";
import { useState, useEffect, useRef } from "react";
import { useSession } from "../context/SessionContext";

const API_URL = "";

export default function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [sessionList, setSessionList] = useState([]);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const { sessionId, loadSession, startNewChat } = useSession();
  const prevSessionIdRef = useRef(null);
  const menuRef = useRef(null);

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

  const handleDeleteSession = async (e, id) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this session?")) return;

    try {
      const res = await fetch(`${API_URL}/sessions/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSessionList(prev => prev.filter(s => s.session_id !== id));
        if (sessionId === id) startNewChat();
        setActiveMenuId(null);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const handleDummyAction = (e, action) => {
    e.stopPropagation();
    alert(`${action} coming soon!`);
    setActiveMenuId(null);
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // Re-fetch session list ONLY when a new session is originated
  useEffect(() => {
    if (sessionId && !prevSessionIdRef.current) {
      fetchSessions();
    }
    prevSessionIdRef.current = sessionId;
  }, [sessionId]);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!activeMenuId) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [activeMenuId]);

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
              onClick={() => {
                loadSession(session.session_id);
                setActiveMenuId(null);
              }}
              className={`sidebar-item ${sessionId === session.session_id ? "active" : ""}`}
            >
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {(() => {
                  const firstMsg = session.chat_logs?.[0];
                  if (!firstMsg) return session.summary?.[0]?.substring(0, 15) || "Unnamed Session";
                  if (typeof firstMsg === 'string') return firstMsg.substring(0, 15).replace("User: ", "");
                  const userMsg = session.chat_logs.find(m => m.role === 'user');
                  return userMsg?.content?.substring(0, 15) || "Search Session";
                })()}
              </div>

              <button
                className="session-menu-trigger"
                onClick={(e) => {
                  e.stopPropagation();
                  if (activeMenuId === session.session_id) {
                    setActiveMenuId(null);
                  } else {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setMenuPos({ top: rect.bottom + 4, left: rect.right - 140 });
                    setActiveMenuId(session.session_id);
                  }
                }}
              >
                ⋮
              </button>

              {activeMenuId === session.session_id && (
                <div
                  ref={menuRef}
                  className="dropdown-menu"
                  style={{ position: 'fixed', top: menuPos.top, left: menuPos.left + 100, right: 'auto' }}
                >
                  <button className="dropdown-item" onClick={(e) => handleDummyAction(e, 'Pin')}> Pin</button>
                  <button className="dropdown-item" onClick={(e) => handleDummyAction(e, 'Archive')}> Archive</button>
                  <button className="dropdown-item" onClick={(e) => handleDummyAction(e, 'Share')}> Share</button>
                  <div style={{ height: "1px", background: "var(--panel-glass-border)", margin: "4px 0" }}></div>
                  <button className="dropdown-item delete" onClick={(e) => handleDeleteSession(e, session.session_id)}>Delete</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
