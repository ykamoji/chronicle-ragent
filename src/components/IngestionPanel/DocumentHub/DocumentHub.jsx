"use client";
import { useState, useEffect, useRef } from "react";
import { useSession } from "../../../context/SessionContext";
import "./DocumentHub.css";
import { API_URL } from "../../../api";
import { LOCAL_TIMEZONE } from "../../../timezone";
import sampleQueries from "../../../../public/sample_queries.json";

const formatDate = (isoDate) => {
  if (!isoDate) return "—";
  try {
    return new Date(isoDate).toLocaleDateString("en-US", {
      timeZone: LOCAL_TIMEZONE,
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch {
    return "—";
  }
};

const handleDownload = async (filename) => {
  const response = await fetch(`/${filename}`);
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

const formatCompact = (num_str) => {

  let num = parseFloat(num_str)
  if (!num) return "0";
  if (num < 1e3) return num.toString();
  if (num < 1e6) return (num / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
  if (num < 1e9) return (num / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  return (num / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
};

const StatCard = ({ icon, label, value }) => (
  <div className="stat-card">
    <div className="stat-icon">{icon}</div>
    <div className="stat-info">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value || "—"}</span>
    </div>
  </div>
);

export default function DocumentHub() {
  const [uploadStatus, setUploadStatus] = useState("");
  const [viewingPdf, setViewingPdf] = useState(null);
  const { sessionId, setSessionId, setCurrentSummaries,
    ingestionProgress, setIngestionProgress, setActiveIngestionTab, sessionList, setSessionList, sessionData, setSessionData } = useSession();
  const ingestion_completed = useRef(false)
  const resumeIngestion = useRef(false)
  const triggeredIngestion = useRef(false)
  const [showResumeButton, setShowResumeButton] = useState(false);
  const stallTimerRef = useRef(null);
  const eventSourceRef = useRef(null);
  const lastProgressRef = useRef({ current: null, phase: null });

  // Resume tracking if session already exists and is ingesting, and fetch session data
  useEffect(() => {
    if (sessionId) {
      if (ingestionProgress &&
        ingestionProgress.phase !== "complete" &&
        ingestionProgress.phase !== "failed") {
        resumeIngestion.current = true
      }
      else {
        resumeIngestion.current = false
      }
    }
    if (sessionId === null && sessionData) {
      setSessionData(null)
    }

  }, [sessionId]);


  useEffect(() => {
    if (ingestion_completed.current && ingestionProgress && ingestionProgress.phase === "complete") {
      const fetchSessionMetadata = async () => {
        try {
          const res = await fetch(`${API_URL}/sessions/${sessionId}`);
          if (res.ok) {
            const data = await res.json();
            setSessionData(data);
            setCurrentSummaries(data.metadata)
            // setActiveIngestionTab("summaries")
            ingestion_completed.current = false
          }
        } catch (err) {
          console.error("Failed to fetch session data:", err);
        }
      };
      fetchSessionMetadata()
    }

    if (!resumeIngestion.current && sessionId && ingestionProgress && ingestionProgress.phase !== "complete") {
      resumeIngestion.current = true
      startProgressStream(sessionId);
    }

  }, [ingestionProgress]);


  useEffect(() => {
    if (ingestionProgress && ingestionProgress.phase !== "complete" && ingestionProgress.phase !== "failed") {
      // If progress or phase changed, reset stall timer
      if (ingestionProgress.current !== lastProgressRef.current.current) {
        lastProgressRef.current = { current: ingestionProgress.current };
        setShowResumeButton(false);

        if (stallTimerRef.current) clearTimeout(stallTimerRef.current);

        stallTimerRef.current = setTimeout(() => {
          setShowResumeButton(true);
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
            triggeredIngestion.current = false;
          }
        }, 90000); // 90 second
      }
    } else {
      // Ingestion finished or not started
      setShowResumeButton(false);
      if (stallTimerRef.current) clearTimeout(stallTimerRef.current);
    }
  }, [ingestionProgress]);


  const handleResumeIngestion = async () => {
    try {
      const res = await fetch(`${API_URL}/resume-ingestion/${sessionId}`);
      if (res.ok) {
        setShowResumeButton(false);
        // Restart the progress stream if it stopped
        if (!triggeredIngestion.current) {
          startProgressStream(sessionId);
        }
      }
    } catch (err) {
      console.error("Failed to resume ingestion:", err);
    }
  };


  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus("Uploading...");
    setIngestionProgress(null); // Reset progress

    const formData = new FormData();
    formData.append("file", file);
    formData.append("filename", file.name);
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
      const activeSessionId = sessionId || data.session_id;

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
        setSessionList(prev => [{ session_id: data.session_id, chat_name: "", source_filename: "" }, ...prev])
      }

      setUploadStatus(`Ingesting ${file.name}...`);

      startProgressStream(activeSessionId);
    } catch (err) {
      console.error(err);
      setUploadStatus("Failed to upload.");
    }
  };

  const handleSampleUpload = async (filename) => {
    const response = await fetch(`/${filename}`);
    const blob = await response.blob();
    const file = new File([blob], filename, { type: "application/pdf" });
    const fakeEvent = { target: { files: [file] } };
    handleFileUpload(fakeEvent);
  };

  const startProgressStream = (id) => {
    if (triggeredIngestion.current) return

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    triggeredIngestion.current = true
    // Direct link to Flask for SSE (bypassing Next.js proxy if needed)
    const sseUrl = `${API_URL}/ingest-progress/${id}`;
    const eventSource = new EventSource(sseUrl);

    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setIngestionProgress(data);

      // Refresh once completed
      if (data.phase === "complete") {
        ingestion_completed.current = true
        setSessionId(id);
        setIngestionProgress(data);
      }

      if (data.phase === "complete" || data.phase === "failed") {
        eventSource.close();
        eventSourceRef.current = null;
        triggeredIngestion.current = false
        if (data.phase === "complete") {
          setUploadStatus("Ingestion complete!");
          // setActiveIngestionTab("summaries")
        } else {
          setUploadStatus(`Ingestion failed: ${data.error || "Unknown error"}`);
        }
      }
    };

    eventSource.onerror = (err) => {
      console.log("SSE Error:", err);
      eventSourceRef.current = null;
      triggeredIngestion.current = false
      eventSource.close();
    };
  };

  const renderProgressBar = (phase, label) => {
    const isActive = ingestionProgress?.phase === phase;
    const isCompleted =
      (phase === "extraction" && ingestionProgress?.phase === "embedding") ||
      ingestionProgress?.phase === "complete";

    const current = ingestionProgress.current > 0 ? ingestionProgress.current - 1 : 0
    let percentage = 0;
    if (isActive && ingestionProgress.total > 0) {
      percentage = Math.round((current / ingestionProgress.total) * 100);
    } else if (isCompleted) {
      percentage = 100;
    }

    return (
      <div className={`progress-stage ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}>
        <div className="stage-header">
          <div className="stage-dot"></div>
          <span className="stage-label">{label}</span>
          {isActive && (
            <span className="stage-count">
              {current}/{ingestionProgress.total}
            </span>
          )}
        </div>
        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${percentage}%` }}
          ></div>
        </div>
      </div>
    );
  };

  const isIngesting = ingestionProgress && ingestionProgress.phase !== "complete" && ingestionProgress.phase !== "failed";

  const currentSession = sessionList.find(session => session.session_id === sessionId)
  let knowledge_available = false
  if (currentSession && currentSession.source_filename && !isIngesting) {
    knowledge_available = true
  }

  const show_live_updated = (!sessionData?.metadata || (ingestionProgress && ingestionProgress.phase !== "complete"))

  return (
    <>
      <h2>Knowledge Hub</h2>

      {/* Current Document Display */}
      {sessionId && !show_live_updated && (
        <>
          <div style={{
            padding: "12px 16px",
            background: "rgba(0, 0, 0, 0.02)",
            border: "1px solid var(--panel-glass-border, rgba(0, 0, 0, 0.08))",
            borderRadius: "8px",
            marginTop: "20px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "12px"
          }}>
            <span style={{ fontSize: "20px" }}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                width="100"
                height="100"
              >
                <path
                  d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"
                  fill="#e53935"
                />
                <path d="M14 2v6h6" fill="#ef5350" />
                <text x="6.5" y="17" fontSize="6" fontFamily="Arial, sans-serif" fill="white">PDF</text>
              </svg>
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-primary)" }}>
                {sessionData?.source_filename || sessionData?.chat_name || `Session ${sessionId.slice(0, 8)}`}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                Uploaded: {formatDate(sessionData?.upload_time)}
              </div>
            </div>
          </div>

          <div className="stats-container">
            <h3>Novel</h3>
            <div className="stats-grid">
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>}
                label="Total Words"
                value={formatCompact(sessionData?.stats?.general?.total_words)}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>}
                label="Chapters"
                value={sessionData?.stats?.general?.total_chapters}
              />
            </div>

            <h3 style={{ marginTop: '24px' }}>Infrastructure</h3>
            <div className="stats-grid">
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M3 5V19A9 3 0 0 0 21 19V5"></path><path d="M3 12A9 3 0 0 0 21 12"></path></svg>}
                label="Total Tokens"
                value={formatCompact(sessionData?.stats?.chunks?.total_tokens)}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>}
                label="Total Chunks"
                value={sessionData?.stats?.chunks?.total_chunks}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><path d="M9 1v3"></path><path d="M15 1v3"></path><path d="M9 20v3"></path><path d="M15 20v3"></path><path d="M20 9h3"></path><path d="M20 15h3"></path><path d="M1 9h3"></path><path d="M1 15h3"></path></svg>}
                label="Chunk Tokens"
                value={formatCompact(Math.round(sessionData?.stats?.chunks?.chunk_tokens))}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>}
                label="Overlap Tokens"
                value={Math.round(sessionData?.stats?.chunks?.overlap_tokens)}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="20" x2="12" y2="10"></line><line x1="18" y1="20" x2="18" y2="4"></line><line x1="6" y1="20" x2="6" y2="16"></line></svg>}
                label="Utilization"
                value={`${sessionData?.stats?.chunks?.chunk_utilization_pct}%`}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>}
                label="Overlap Redundancy"
                value={`${sessionData?.stats?.chunks?.overlap_redundancy_pct}%`}
              />
            </div>
            <h3 style={{ marginTop: '24px' }}>Quality Metrics</h3>
            <div className="stats-grid">
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>}
                label="Lexical Density"
                value={`${sessionData?.stats?.quality?.lexical_density}%`}
              />
              <StatCard
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="9" x2="20" y2="9"></line><line x1="4" y1="15" x2="20" y2="15"></line><line x1="10" y1="3" x2="8" y2="21"></line><line x1="16" y1="3" x2="14" y2="21"></line></svg>}
                label="Unique Words"
                value={formatCompact(Math.round(sessionData?.stats?.quality?.unique_words))}
              />
            </div>
          </div>
        </>
      )}

      {show_live_updated && !knowledge_available && <>
        {!ingestionProgress ? (
          <>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "16px", marginTop: "16px" }}>
              Upload PDF or text files to build the agent&apos;s knowledge base.
            </p>
            <div
              className="file-drop-zone"
              onClick={() => document.getElementById("file-upload").click()}
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
            <div style={{ textAlign: "center", marginTop: "10px", marginBottom: "10px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>OR use a sample</div>
            <div className="pdf-picker">
              {Object.keys(sampleQueries).map((filename) => (
                <div key={filename} className="pdf-group">
                  <button
                    className="pdf-btn"
                    type="button"
                    onClick={() => handleSampleUpload(filename)}
                    title={`Ingest ${filename}`}
                    style={{ background: "none", display: "flex", flexDirection: "column", border: "none", cursor: "pointer", padding: 0 }}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="80" height="80">
                      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#e53935" />
                      <path d="M14 2v6h6" fill="#ef5350" />
                      <text x="6.5" y="17" fontSize="6" fontFamily="Arial, sans-serif" fill="white">PDF</text>
                    </svg>
                    <span style={{ fontSize: "0.80rem", color: "var(--text-secondary)", wordBreak: "break-word", lineHeight: 1.3 }}>
                      {filename}
                    </span>
                  </button>
                  <div style={{ display: "flex", gap: "4px" }}>
                    <button
                      className="pdf-btn pdf-btn-mini"
                      type="button"
                      onClick={() => handleDownload(filename)}
                      title="Download"
                      style={{ border: "1px solid var(--panel-glass-border, rgba(0,0,0,0.1))", cursor: "pointer", padding: "3px 5px", display: "flex" }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                    </button>
                    <button
                      className="pdf-btn pdf-btn-mini"
                      type="button"
                      onClick={() => setViewingPdf(filename)}
                      title="Preview"
                      style={{ border: "1px solid var(--panel-glass-border, rgba(0,0,0,0.1))", cursor: "pointer", padding: "3px 5px", display: "flex" }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (<>
          <div className="ingestion-stepper">
            <div className="stepper-rail"></div>
            {renderProgressBar("extraction", "Stage 1: Metadata Extraction")}
            {renderProgressBar("embedding", "Stage 2: Embedding Generation")}
          </div>
          {showResumeButton && (
            <button
              type="button"
              className="resume-ingestion-btn"
              onClick={handleResumeIngestion}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
              Resume
            </button>
          )}
        </>
        )}</>
      }

      {
        uploadStatus && !ingestionProgress && (
          <div style={{ padding: "12px", borderRadius: "8px", fontSize: "0.9rem", marginTop: "20px" }}>
            <div
              style={{
                position: "relative",
                height: "8px",
                width: "100%",
                overflow: "hidden",
                borderRadius: "999px",
                background: "rgba(0,0,0,0.08)",
              }}
            >
              <div className="indeterminate-bar" />
            </div>
          </div>
        )
      }

      {viewingPdf && (
        <div
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center" }}
          onClick={() => setViewingPdf(null)}
        >
          <div
            style={{ width: "min(900px, 92vw)", height: "88vh", background: "#fff", overflow: "hidden", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", borderBottom: "1px solid #e5e7eb", background: "#f9fafb", flexShrink: 0 }}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" style={{ flexShrink: 0 }}>
                <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#e53935" />
                <path d="M14 2v6h6" fill="#ef5350" />
                <text x="6.5" y="17" fontSize="6" fontFamily="Arial, sans-serif" fill="white">PDF</text>
              </svg>
              <span style={{ flex: 1, fontSize: "13px", fontWeight: "500", color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{viewingPdf}</span>
              <button
                type="button"
                onClick={() => handleDownload(viewingPdf)}
                title="Download"
                style={{ background: "none", border: "1px solid #e5e7eb", cursor: "pointer", padding: "5px 8px", display: "flex", alignItems: "center", gap: "5px", fontSize: "12px", color: "#374151" }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                Download
              </button>
              <button
                type="button"
                onClick={() => setViewingPdf(null)}
                title="Close"
                style={{ background: "none", border: "1px solid #e5e7eb", cursor: "pointer", padding: "5px 8px", display: "flex", alignItems: "center", color: "#374151" }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
              </button>
            </div>
            <iframe
              src={`/${viewingPdf}`}
              style={{ flex: 1, border: "none", display: "block" }}
              title={viewingPdf}
            />
          </div>
        </div>
      )}
    </>
  );
}
