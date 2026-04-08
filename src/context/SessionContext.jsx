"use client";
import { createContext, useContext, useState, useCallback } from "react";

const SessionContext = createContext(null);

const API_URL = "";

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentSummaries, setCurrentSummaries] = useState([]);

  const loadSession = useCallback(async (id) => {
    try {
      const res = await fetch(`${API_URL}/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setCurrentSummaries(data.summary || []);

        if (data.chat_logs && data.chat_logs.length > 0) {
          const parsedMsgs = data.chat_logs.map((log) => {
            const colonIdx = log.indexOf(": ");
            if (colonIdx !== -1) {
              return {
                role: log.substring(0, colonIdx).toLowerCase(),
                content: log.substring(colonIdx + 2),
              };
            }
            return { role: "system", content: log };
          });
          setMessages(parsedMsgs);
        } else {
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("Failed to load session", err);
    }
  }, []);

  const startNewChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setCurrentSummaries([]);
  }, []);

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
