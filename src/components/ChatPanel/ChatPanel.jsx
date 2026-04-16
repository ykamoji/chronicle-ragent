"use client";
import { useState, useRef, useEffect } from "react";
import { useSession } from "../../context/SessionContext";
import ReactMarkdown from 'react-markdown';
import { CollapsibleObservation } from "./Observations/Observation";
import "./ChatPanel.css";
import { API_URL } from "../../api";
import { LOCAL_TIMEZONE } from "../../timezone";


// Direct to Flask for SSE streaming (bypasses Next.js proxy buffering)

export const renderStepAction = (action) => {
  if (!action) return null;

  const match = action.match(/^(\w+)\[(.*)\]$/);

  // fallback (no match)
  if (!match) {
    return <div className="step-action">{action}</div>;
  }

  const rawTool = match[1];
  const tool = match[1]
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const query = match[2];

  return (
    <div className="step-action">
      <span className="step-tool">{tool}</span>
      {rawTool !== "finish" && (
        <span className="step-chip">{tool === 'Summary' ? (query || 'All') : query}</span>
      )}
    </div>
  );
};

const formatTime = (isoString) => {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      timeZone: LOCAL_TIMEZONE,
      day: "2-digit",
      month: "short",   // Apr, May, etc.
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,    // no AM/PM
    });
  } catch (e) {
    return "";
  }
};

const formatTimeWithSeconds = (isoString) => {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      timeZone: LOCAL_TIMEZONE,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch (e) {
    return "";
  }
};

/** Calls /query/cleanup to purge the failed round from MongoDB. */
const callCleanup = async (sid) => {
  if (!sid) return;
  try {
    await fetch(`${API_URL}/query/cleanup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid }),
    });
  } catch (e) {
    console.warn("Cleanup call failed:", e);
  }
};

export default function ChatPanel() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [sampleQueries, setSampleQueries] = useState([]);
  const [streamSessionId, setStreamSessionId] = useState(null);
  const [expandedSteps, setExpandedSteps] = useState({}); // Tracks which message reasoning is expanded
  const chatWindowRef = useRef(null);
  const liveThoughtsRef = useRef(null);
  const {
    sessionId, setSessionId, messages, currentSummaries,
    setMessages, isSessionLoading, loadSession, sessionList, setSessionList,
    setActiveIngestionTab, setHighlightChapter, setReferenceText,
    setIsPanelExpanded
  } = useSession();

  const abortControllerRef = useRef(null);

  const agentAnswerRef = useRef(false);
  const agentChatRef = useRef(sessionList.find(s => s.session_id === sessionId)?.chat_name)

  const handleStop = async () => {
    if (!sessionId) return;

    // 1. Signal backend to stop
    try {
      await fetch(`${API_URL}/query/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (e) {
      console.warn("Stop signal failed:", e);
    }

    // 2. Abort frontend request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort("User stopped generation");
    }

    // 3. Cleanup and UI state
    setIsLoading(false);
    await callCleanup(sessionId);
  };

  const currentSessionIdRef = useRef(sessionId);
  useEffect(() => {
    currentSessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    fetch("/sample_queries.json")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.queries) {
          setSampleQueries(data.queries);
        }
      })
      .catch((err) => console.error("Failed to load sample queries:", err));
  }, []);

  const isStreamVisible = sessionId === streamSessionId;

  const handleSourceClick = (sourceName) => {
    setActiveIngestionTab("summaries");
    setHighlightChapter(sourceName);
    setIsPanelExpanded(true);
  };

  const handleBlockClick = async (blockText) => {
    if (!blockText || !sessionId) return;

    try {
      // Direct call to Flask (bypassing Next.js proxy if needed)
      const res = await fetch(`${API_URL}/vectors/${sessionId}`);
      if (!res.ok) return;
      const vectors = await res.json();

      // Match the text using the first ~80 chars to be safe against truncation/formatting
      const snippet = blockText.trim().substring(0, 80).toLowerCase();
      const matchedDoc = vectors.find(doc => doc.text.trim().toLowerCase().startsWith(snippet));

      if (matchedDoc) {
        setReferenceText(`[Source: ${matchedDoc.chapter} #${matchedDoc.parent_chapter_index + 1}]\n\n${matchedDoc.text}`);
        setActiveIngestionTab("reference");
        setIsPanelExpanded(true);
      } else {
        const matchedDocSummary = currentSummaries.find(doc => doc.summary.trim().toLowerCase().startsWith(snippet));

        if (matchedDocSummary) {
          handleSourceClick(matchedDocSummary.chapter);
        }
        else {
          // Fallback: just show the snippet if no match
          setReferenceText(`Couldn't find full source text. Snippet:\n\n${blockText}`);
          setActiveIngestionTab("reference");
          setIsPanelExpanded(true);
        }
      }
    } catch (err) {
      console.error("Failed to fetch full reference text:", err);
    }
  };

  // Auto-scroll chat
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading, agentSteps]);


  /** Re-submits the last query. */
  const handleRetry = async () => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role !== "user") return;

    const retryQuery = lastMsg.content;

    // 1. Remove the last user message from local state
    setMessages((prev) => prev.slice(0, -1));
    setQuery(retryQuery);

    // 2. Clean up the failed attempt from the backend first
    if (sessionId) {
      await callCleanup(sessionId);
    }

    // 3. Submit immediately
    handleSend(null, retryQuery);
  };

  const handleSend = async (e, overrideQuery) => {
    e?.preventDefault();
    const userQuery = (overrideQuery ?? query).trim();
    if (!userQuery) return;

    setQuery("");
    setMessages((prev) => [...prev, { role: "user", content: userQuery, timestamp: new Date().toLocaleString("en-US", { timeZone: LOCAL_TIMEZONE }) }]);
    setIsLoading(true);
    setAgentSteps([]); // Clear previous steps at start of new query
    setStreamSessionId(sessionId || null);

    let currentSessionId = sessionId;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const payload = { query: userQuery };
      if (sessionId) payload.session_id = sessionId;

      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error("API request failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalAnswer = null;
      let receivedSessionId = null;
      let responseModel = null;
      let responseTime = null;
      let currentSteps = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            switch (event.type) {
              case "thought":
                const thoughtObj = {
                  type: "thought",
                  content: event.content,
                  action: event.action,
                  time: event.time
                };
                setAgentSteps((prev) => [...prev, thoughtObj]);
                currentSteps.push(thoughtObj);
                break;

              case "tool":
                const toolObj = {
                  type: "tool",
                  tool: event.tool,
                  args: event.args,
                  time: event.time
                };
                setAgentSteps((prev) => [...prev, toolObj]);
                currentSteps.push(toolObj);
                break;

              case "observation":
                const obsObj = {
                  type: "observation",
                  content: event.content,
                  time: event.time
                };
                setAgentSteps((prev) => [...prev, obsObj]);
                currentSteps.push(obsObj);
                break;

              case "answer":
                finalAnswer = event.content;
                receivedSessionId = event.session_id;
                responseModel = event.model_name;
                responseTime = event.total_time;
                break;

              case "chat_name":
                agentChatRef.current = event.chat_name
                break;

              case "error":
                // Handled in backend + state drive UI
                const errObj = {
                  type: "error",
                  content: event.content,
                  time: event.time
                };
                setAgentSteps((prev) => [...prev, errObj]);
                currentSteps.push(errObj);
                // STOP immediately on error
                if (reader) reader.cancel();
                break;
            }
          } catch (parseErr) {
            console.warn("Failed to parse SSE event:", parseErr);
          }
        }
        // If we hit an error, the break above was for the for-loop, 
        // we need to break the while-loop too if errObj was pushed.
        if (currentSteps.length > 0 && currentSteps[currentSteps.length - 1].type === "error") {
          break;
        }
      }

      if (receivedSessionId) {
        currentSessionId = receivedSessionId;
        setStreamSessionId(receivedSessionId);
        if (!sessionId) setSessionId(receivedSessionId);
      }

      if (finalAnswer) {
        if (currentSessionIdRef.current === currentSessionId) {
          setMessages((prev) => [
            ...prev,
            { role: "agent", content: finalAnswer, timestamp: new Date().toLocaleString("en-US", { timeZone: LOCAL_TIMEZONE }), steps: currentSteps, model_name: responseModel, total_time: responseTime },
          ]);
          agentAnswerRef.current = true
        }
      } else {
        // Did not finish — ensure cleanup
        await callCleanup(currentSessionId);
      }

    } catch (err) {
      console.log("Error ", err);
      await callCleanup(currentSessionId);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {

    if (!isLoading && agentAnswerRef.current && sessionId) {
      const task = async () => await loadSession(sessionId, true);
      task()
      if (agentChatRef.current !== null) {
        setSessionList(prev =>
          prev.map(s =>
            s.session_id === sessionId
              ? { ...s, chat_name: agentChatRef.current }
              : s
          )
        );
      }

      agentAnswerRef.current = false
    }
  }, [isLoading])

  // const scrollToBottom = () => {
  //   if (liveThoughtsRef.current) {
  //     liveThoughtsRef.current.scrollIntoView({ behavior: "smooth" });
  //   }
  // };

  // useEffect(() => {
  //   scrollToBottom();
  // }, [agentSteps]);

  return (
    <main className="chat-container glass-panel">
      <div style={{ padding: "24px", borderBottom: "1px solid var(--panel-glass-border)" }}>
        <h1>Chronicle <span style={{ color: "var(--accent-cyan)" }}>Chat</span></h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Real-time RAG inference powered by ReAct
        </p>
      </div>

      <div className="chat-window" ref={chatWindowRef}>
        {!isSessionLoading && messages.length === 0 && !isLoading && (
          <div style={{ margin: "auto", textAlign: "center", color: "var(--text-secondary)" }}>
            <h2>Start a conversation</h2>
            <p>Ask about characters, plots, or relationships.</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} style={{ marginBottom: "16px", display: "flex", flexDirection: "column" }}>
            <div className={`chat-bubble ${msg.role}`}>
              <div className="chat-content">
                <ReactMarkdown>
                  {msg.content}
                </ReactMarkdown>
              </div>
              {msg.timestamp && (
                <div className="chat-timestamp" style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                  {formatTime(msg.timestamp)}
                </div>
              )}
            </div>
            {msg.role === "agent" && msg.steps && msg.steps.length > 0 && (
              <div className="reasoning-toggle">
                <button
                  className="reasoning-toggle-btn"
                  onClick={() => setExpandedSteps(prev => ({ ...prev, [index]: !prev[index] }))}
                >
                  View reasoning
                  <div className={`chevron ${expandedSteps[index] ? "open" : ""}`}>
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 20 20"
                      fill="none"
                    >
                      <path
                        d="M6 12L10 8L14 12"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="square"
                        strokeLinejoin="miter"
                      />
                    </svg>
                  </div>
                </button>
              </div>
            )}

            {/* Collapsible Reasoning Block */}
            {msg.role === "agent" && msg.steps && msg.steps.length > 0 && expandedSteps[index] && (
              <>
                {(msg.model_name || msg.total_time) && (
                  <div className="agent-meta-info">
                    <span>{msg.model_name && `${msg.model_name}`}</span>
                    <span>{msg.total_time && `${msg.total_time}s`}</span>
                  </div>
                )}
                <div className="agent-steps-container historical">
                  {msg.steps.filter(step => step.type !== "tool").map((step, si) => (
                    <div key={si} className={`agent-step ${step.type}`}>
                      {step.type === "thought" && (
                        <div>
                          <span className="step-text">{<ReactMarkdown>{step.content}</ReactMarkdown> || "Thinking"}</span>
                          {renderStepAction(step.action)}
                        </div>
                      )}
                      {step.type === "observation" && (
                        <CollapsibleObservation
                          content={step.content}
                          onSourceClick={handleSourceClick}
                          onBlockClick={handleBlockClick}
                        />
                      )}
                      {step.type === "error" && (
                        <div>
                          <span className="step-text error-text">{step.content}</span>
                        </div>
                      )}
                      <div className="step-time">{formatTimeWithSeconds(step.time)}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ))}

        {/* Live Agent Reasoning Steps 
            Persistent if last message is a user question (failed query) */}
        {isStreamVisible && (isLoading || (messages.length > 0 && messages[messages.length - 1].role === "user")) && agentSteps.length > 0 && (
          <div className="agent-steps-container live">
            {agentSteps.filter(step => step.type !== "tool").map((step, i) => (
              <div key={i} className={`agent-step ${step.type}`}>
                {step.type === "thought" && (
                  <div>
                    <span className="step-text">{step.content || "Thinking"}</span>
                    {renderStepAction(step.action)}
                    <div style={{ opacity: 0.7 }}>{formatTimeWithSeconds(step.time)}</div>
                  </div>
                )}
                {step.type === "observation" && (
                  <>
                    <CollapsibleObservation
                      content={step.content}
                      onSourceClick={handleSourceClick}
                      onBlockClick={handleBlockClick}
                    />
                    <div style={{ opacity: 0.7 }}>{formatTimeWithSeconds(step.time)}</div>
                  </>
                )}
                {step.type === "error" && (
                  <div>
                    <span className="step-text error-text">{step.content}</span>
                    <div style={{ opacity: 0.7 }}>{formatTimeWithSeconds(step.time)}</div>
                  </div>
                )}
              </div>
            ))}

            {/* Spinner: ONLY if loading AND no error encountered yet */}
            {isLoading && !agentSteps.some(s => s.type === "error") && (
              <div className="agent-step loading">
                <div className="loader"></div>
                <span className="step-text">Thinking...</span>
              </div>
            )}
            <div ref={liveThoughtsRef} />
          </div>
        )}

        {isStreamVisible && isLoading && agentSteps.length === 0 && (
          <div className="chat-bubble agent">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="loader"></div> Planning...
            </div>
          </div>
        )}

        {/* Global Retry Option: If last message is User and we are not loading, the agent failed to respond. */}
        {!isLoading && messages.length > 0 && messages[messages.length - 1].role === "user" && (
          <div className="retry-row">
            <span className="retry-label">Error</span>
            <button
              className="retry-btn"
              onClick={handleRetry}
            >
              ↩ Retry
            </button>
          </div>
        )}
      </div>

      {/* Session loading: bouncing typing dots at the bottom of the chat area */}
      {isSessionLoading && messages.length == 0 && (
        <div className="session-loading-row">
          <div className="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span className="session-loading-label">Loading conversation…</span>
        </div>
      )}

      {!isLoading && sampleQueries.length > 0 && (
        <div className="sample-queries-container">
          {sampleQueries.map((q, idx) => (
            <button
              key={idx}
              className="sample-query-chip"
              onClick={() => handleSend(null, q)}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <form className="chat-input-area" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Ask the agent anything..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isLoading || isSessionLoading}
        />
        {isLoading ? (
          <button type="button" className="stop-btn" onClick={handleStop} >
            <span className="stop-icon"></span>
          </button>
        ) : (
          <button type="submit" disabled={isSessionLoading}>
            Ask
          </button>
        )}
      </form>
    </main>
  );
}
