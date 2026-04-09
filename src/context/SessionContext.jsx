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
        setCurrentSummaries(data.metadata || []);

        if (data.chat_logs && data.chat_logs.length > 0) {
          const parsedMsgs = [];
          let pendingSteps = [];

          data.chat_logs.forEach((msg) => {
            if (typeof msg !== 'object') return;

            if (msg.is_hidden) {
              const content = msg.content || "";
              if (content.startsWith("Thought:")) {
                const thoughtMatch = content.match(/Thought:\s*(.*?)(?=Action:|$)/s);
                const actionMatch = content.match(/Action:\s*(\w+)\[(.*?)\]/s);
                pendingSteps.push({
                  type: "thought",
                  content: thoughtMatch ? thoughtMatch[1].trim() : content,
                  action: actionMatch ? `${actionMatch[1]}[${actionMatch[2]}]` : null
                });
              } else if (content.startsWith("Observation:")) {
                pendingSteps.push({
                  type: "observation",
                  content: content.replace("Observation: ", "").trim()
                });
              }
            } else {
              // Visible message
              const message = { ...msg };
              if (msg.role === "agent") {
                message.steps = [...pendingSteps];
                pendingSteps = [];
              }
              parsedMsgs.push(message);
            }
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
