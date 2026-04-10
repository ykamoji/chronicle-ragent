"use client";
import { useState, useRef, useEffect } from "react";
import { useSession } from "../context/SessionContext";
import { CollapsibleObservation } from "./Observation";
import "./ChatPanel.css";

const STREAM_URL = "http://127.0.0.1:5328"; // Direct to Flask for SSE streaming (bypasses Next.js proxy buffering)

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
        <span className="step-chip">{query}</span>
      )}
    </div>
  );
};

export default function ChatPanel() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [expandedSteps, setExpandedSteps] = useState({}); // Tracks which message reasoning is expanded
  const chatWindowRef = useRef(null);
  const { sessionId, setSessionId, messages, setMessages, loadSession } = useSession();

  // Auto-scroll chat
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading, agentSteps]);

  const formatTime = (isoString) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleString("en-GB", {
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
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false, // ✅ removes AM/PM
      });
    } catch (e) {
      return "";
    }
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;

    const userQuery = query.trim();
    setQuery("");
    setMessages((prev) => [...prev, { role: "user", content: userQuery, timestamp: new Date().toISOString() }]);
    setIsLoading(true);
    setAgentSteps([]);

    let currentSessionId = sessionId;

    try {
      const payload = { query: userQuery };
      if (sessionId) payload.session_id = sessionId;

      const res = await fetch(`${STREAM_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("API request failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalAnswer = null;
      let receivedSessionId = null;
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
                break;

              case "error":
                const errObj = {
                  type: "error",
                  content: event.content,
                  time: event.time
                };
                setAgentSteps((prev) => [...prev, errObj]);
                currentSteps.push(errObj);
                break;
            }
          } catch (parseErr) {
            console.warn("Failed to parse SSE event:", parseErr);
          }
        }
      }

      if (receivedSessionId) {
        currentSessionId = receivedSessionId;
        if (!sessionId) setSessionId(receivedSessionId);
      }

      if (finalAnswer) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: finalAnswer, timestamp: new Date().toISOString(), steps: currentSteps },
        ]);
      } else {
        // No answer event received — check if there was an error
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: "The agent could not produce a final answer.", timestamp: new Date().toISOString(), steps: currentSteps },
        ]);
      }

      // Refresh ChatPanel from server to ensure local state matches DB exactly (especially reasoning steps)
      if (currentSessionId) {
        await loadSession(currentSessionId, true);
      }

    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Connection error. The backend may be unavailable. Please try again.", timestamp: new Date().toISOString() },
      ]);
    } finally {
      setIsLoading(false);
      setAgentSteps([]);
    }
  };

  return (
    <main className="chat-container glass-panel">
      <div style={{ padding: "24px", borderBottom: "1px solid var(--panel-glass-border)" }}>
        <h1>Chronicle <span style={{ color: "var(--accent-cyan)" }}>Chat</span></h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Real-time RAG inference powered by ReAct
        </p>
      </div>

      <div className="chat-window" ref={chatWindowRef}>
        {messages.length === 0 && !isLoading && (
          <div style={{ margin: "auto", textAlign: "center", color: "var(--text-secondary)" }}>
            <h2>Start a conversation</h2>
            <p>Ask about characters, summaries, or specific text segments.</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} style={{ marginBottom: "16px", display: "flex", flexDirection: "column" }}>
            <div className={`chat-bubble ${msg.role}`}>
              <div className="chat-content">
                {msg.content.split("\n").map((line, i) => (
                  <span key={i}>
                    {line}
                    <br />
                  </span>
                ))}
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
              <div className="agent-steps-container historical">
                {msg.steps.filter(step => step.type !== "tool").map((step, si) => (
                  <div key={si} className={`agent-step ${step.type}`}>
                    {step.type === "thought" && (
                      <div>
                        <span className="step-text">{step.content || "Thinking"}</span>
                        {renderStepAction(step.action)}
                      </div>
                    )}
                    {step.type === "observation" && (
                      <CollapsibleObservation content={step.content} />
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
            )}
          </div>
        ))}

        {/* Live Agent Reasoning Steps */}
        {isLoading && agentSteps.length > 0 && (
          <div className="agent-steps-container">
            {agentSteps.filter(step => step.type !== "tool").map((step, i) => (
              <div key={i} className={`agent-step ${step.type}`}>
                {step.type === "thought" && (
                  <div>
                    <span className="step-text">{step.content || "Thinking"}</span>
                    {renderStepAction(step.action) || "Thinking"}
                    <div style={{ opacity: 0.7 }}>{formatTimeWithSeconds(step.time)}</div>
                  </div>
                )}
                {step.type === "observation" && (
                  <>
                    <CollapsibleObservation content={step.content} />
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
            <div className="agent-step loading">
              <div className="loader"></div>
              <span className="step-text">Thinking...</span>
            </div>
          </div>
        )}

        {isLoading && agentSteps.length === 0 && (
          <div className="chat-bubble agent">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="loader"></div> Planning...
            </div>
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
          Ask
        </button>
      </form>
    </main>
  );
}
