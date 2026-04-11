"use client";
import { createContext, useContext, useState, useCallback, useEffect } from "react";

const SessionContext = createContext(null);

const API_URL = "";

export function SessionProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentSummaries, setCurrentSummaries] = useState([]);
  const [ingestionProgress, setIngestionProgress] = useState(null);
  const [sessionsCache, setSessionsCache] = useState({});

  const loadSession = useCallback(async (id, forceRefresh = false) => {
    // Check cache first unless forced to refresh
    if (!forceRefresh && sessionsCache[id]) {
      const cached = sessionsCache[id];
      setSessionId(id);
      setMessages(cached.messages || []);
      setCurrentSummaries(cached.summaries || []);
      return;
    }

    try {
      const [sessRes, msgRes] = await Promise.all([
        fetch(`${API_URL}/sessions/${id}`),
        fetch(`${API_URL}/messages/${id}`)
      ]);

      if (sessRes.ok && msgRes.ok) {
        const data = await sessRes.json();
        const chatLogs = await msgRes.json();

        setSessionId(data.session_id);
        setCurrentSummaries(data.metadata || []);
        setIngestionProgress(data.ingestion_progress || null);

        if (chatLogs && chatLogs.length > 0) {
          const parsedMsgs = [];
          let pendingSteps = [];

          chatLogs.forEach((msg) => {
            if (typeof msg !== 'object') return;

            if (msg.is_hidden) {
              const content = msg.content || "";
              if (content.startsWith("Thought:")) {
                const thoughtMatch = content.match(/Thought:\s*(.*?)(?=Action:|$)/s);
                const actionMatch = content.match(/Action:\s*(\w+)\[(.*?)\]/s);
                pendingSteps.push({
                  type: "thought",
                  content: thoughtMatch ? thoughtMatch[1].trim() : content,
                  action: actionMatch ? `${actionMatch[1]}[${actionMatch[2]}]` : null,
                  time: msg.timestamp
                });
              } else if (content.startsWith("Observation:")) {
                pendingSteps.push({
                  type: "observation",
                  content: content.replace("Observation: ", "").trim(),
                  time: msg.timestamp
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
    setIngestionProgress(null);
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
        ingestionProgress,
        setIngestionProgress,
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
