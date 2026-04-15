"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "../../context/SessionContext";
import ConfirmDialog from "../Helpers/ConfirmDialog";
import SettingsPanel from "./Settings/SettingsPanel";
import "./Sidebar.css";
import { API_URL } from "../../api";

export default function Sidebar() {
  const router = useRouter();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const { sessionId, loadSession, startNewChat, sessionList, setSessionList, fetchSessions } = useSession();
  const menuRef = useRef(null);

  const handleDeleteClick = (e, id) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setPendingDeleteId(id);
  };

  const confirmDelete = async () => {
    const id = pendingDeleteId;
    setPendingDeleteId(null);
    try {
      const res = await fetch(`${API_URL}/sessions/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSessionList(prev => prev.filter(s => s.session_id !== id));
        if (sessionId === id) startNewChat();
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
      <div className="sidebar-header" style={{ display: "flex", justifyContent: isCollapsed ? "center" : "space-between", gap: "8px", marginBottom: "8px" }}>
        <div className="adp-logo" style={{ display: isCollapsed ? "none" : "flex", alignItems: "center" }} onClick={() => router.push("/")}>
          <div className="adp-logo-dot" />
          <span>Chronicle</span>
        </div>
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

      {
        !isCollapsed && (
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
                {session.chat_name || `Session ${session.session_id.slice(0, 8)}`}
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
                    <button className="dropdown-item delete" onClick={(e) => handleDeleteClick(e, session.session_id)}>Delete</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      }

      <SettingsPanel isCollapsed={isCollapsed} />

      <ConfirmDialog
        open={!!pendingDeleteId}
        title="Delete Session"
        message="This will permanently delete the session and all associated data. This action cannot be undone."
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </aside >
  );
}
