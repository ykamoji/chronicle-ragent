"use client";
import { createContext, useContext, useState, useCallback, useEffect } from "react";

const SessionContext = createContext(null);

const API_URL = "";

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentSummaries, setCurrentSummaries] = useState([]);
  const [sessionsCache, setSessionsCache] = useState({});

  const loadSession = useCallback(async (id) => {
    // Check cache first
    if (sessionsCache[id]) {
      const cached = sessionsCache[id];
      setSessionId(id);
      setMessages(cached.messages || []);
      setCurrentSummaries(cached.summaries || []);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setCurrentSummaries(data.summary || []);

        if (data.chat_logs && data.chat_logs.length > 0) {
          // If the message is a structured object, use it directly.
          // Filter out internal hidden steps for the main chat UI.
          const parsedMsgs = data.chat_logs
            .filter(msg => typeof msg === 'object' && !msg.is_hidden)
            .map((msg) => {
              if (typeof msg === 'string') {
                // Fallback for legacy strings if they slip through
                const colonIdx = msg.indexOf(": ");
                return colonIdx !== -1 ? {
                  role: msg.substring(0, colonIdx).toLowerCase(),
                  content: msg.substring(colonIdx + 2),
                } : { role: "system", content: msg };
              }
              return msg;
            });
          setMessages(parsedMsgs);
        } else {
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("Failed to load session", err);
    }
  }, [sessionsCache]);

  const startNewChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setCurrentSummaries([]);
  }, []);

  // Auto-sync local state to cache whenever it changes for the active session
  useEffect(() => {
    if (sessionId) {
      setSessionsCache(prev => ({
        ...prev,
        [sessionId]: {
          messages: messages,
          summaries: currentSummaries
        }
      }));
    }
  }, [messages, currentSummaries, sessionId]);

  return (
    <SessionContext.Provider
      value={{
        sessionId,
        setSessionId,
        messages,
        setMessages,
        currentSummaries,
        setCurrentSummaries,
        loadSession,
        startNewChat,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
