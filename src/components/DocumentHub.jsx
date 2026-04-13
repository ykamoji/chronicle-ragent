"use client";
import { useState, useEffect } from "react";
import { useSession } from "../context/SessionContext";
import { API_URL } from "../api.ts"
import "./DocumentHub.css";

export default function DocumentHub() {
  const [uploadStatus, setUploadStatus] = useState("");
  const [sessionData, setSessionData] = useState(null);
  const { sessionId, setSessionId, loadSession, ingestionProgress, setIngestionProgress, setActiveIngestionTab } = useSession();

  // Resume tracking if session already exists and is ingesting, and fetch session data
  useEffect(() => {
    if (sessionId) {
      const fetchSessionData = async () => {
        try {
          const res = await fetch(`${API_URL}/sessions/${sessionId}`);
          if (res.ok) {
            const data = await res.json();
            setSessionData(data);
            if (data.ingestion_progress &&
              data.ingestion_progress.phase !== "complete" &&
              data.ingestion_progress.phase !== "failed") {
              setIngestionProgress(data.ingestion_progress);
              startProgressStream(sessionId);
            }
          }
        } catch (err) {
          console.error("Failed to fetch session data:", err);
        }
      };

      fetchSessionData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

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
      }

      setUploadStatus(`Ingesting ${file.name}...`);
      startProgressStream(activeSessionId);
    } catch (err) {
      console.error(err);
      setUploadStatus("Failed to upload.");
    }
  };

  const startProgressStream = (id) => {
    // Direct link to Flask for SSE (bypassing Next.js proxy if needed)
    const sseUrl = `${API_URL}/ingest-progress/${id}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const prevProgress = ingestionProgress;
      setIngestionProgress(data);

      // Refresh summaries if phase changes or extraction makes progress
      if (data.phase === "complete" || (data.phase === "extraction" && data.current !== prevProgress?.current)) {
        loadSession(id, true);
      }

      if (data.phase === "complete" || data.phase === "failed") {
        eventSource.close();
        if (data.phase === "complete") {
          setUploadStatus("Ingestion complete!");
          setActiveIngestionTab("summaries")
        } else {
          setUploadStatus(`Ingestion failed: ${data.error || "Unknown error"}`);
        }
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
      eventSource.close();
    };
  };

  const renderProgressBar = (phase, label) => {
    const isActive = ingestionProgress?.phase === phase;
    const isCompleted =
      (phase === "extraction" && ingestionProgress?.phase === "embedding") ||
      ingestionProgress?.phase === "complete";

    let percentage = 0;
    if (isActive && ingestionProgress.total > 0) {
      percentage = Math.round((ingestionProgress.current / ingestionProgress.total) * 100);
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
              {ingestionProgress.current}/{ingestionProgress.total}
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

  const formatDate = (isoDate) => {
    if (!isoDate) return "—";
    try {
      return new Date(isoDate).toLocaleDateString("en-US", {
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

  return (
    <>
      <h2>Document Hub</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "16px" }}>
        Upload PDF or text files to build the agent&apos;s knowledge base.
      </p>

      {/* Current Document Display */}
      {sessionId && sessionData?.metadata && (
        <div style={{
          padding: "12px 16px",
          background: "rgba(0, 0, 0, 0.02)",
          border: "1px solid var(--panel-glass-border, rgba(0, 0, 0, 0.08))",
          borderRadius: "8px",
          marginBottom: "16px",
          display: "flex",
          alignItems: "center",
          gap: "12px"
        }}>
          <span style={{ fontSize: "20px" }}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="24"
              height="24"
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
              {sessionData.source_filename || sessionData.chat_name || `Session ${sessionId.slice(0, 8)}`}
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
              Uploaded: {formatDate(sessionData.upload_time)}
            </div>
          </div>
        </div>
      )}

      {!sessionData?.metadata && <>
        {!ingestionProgress || ingestionProgress.phase === "complete" || ingestionProgress.phase === "failed" ? (
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
        ) : (
          <div className="ingestion-stepper">
            <div className="stepper-rail"></div>
            {renderProgressBar("extraction", "Stage 1: Metadata Extraction")}
            {renderProgressBar("embedding", "Stage 2: Embedding Generation")}
          </div>
        )}</>
      }

      {uploadStatus && !ingestionProgress && (
        <div style={{ padding: "12px", background: "var(--sys-msg-bg)", borderRadius: "8px", fontSize: "0.9rem", marginTop: "16px" }}>
          {uploadStatus}
        </div>
      )}
    </>
  );
}
