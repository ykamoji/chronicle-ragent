"use client";
import { useState, useEffect } from "react";
import { useSession } from "../context/SessionContext";
import "./DocumentHub.css";

const API_URL = "";

export default function DocumentHub() {
  const [uploadStatus, setUploadStatus] = useState("");
  const { sessionId, setSessionId, loadSession, ingestionProgress, setIngestionProgress } = useSession();

  // Resume tracking if session already exists and is ingesting
  useEffect(() => {
    if (sessionId) {
      const fetchSessionProgress = async () => {
        try {
          const res = await fetch(`${API_URL}/sessions/${sessionId}`);
          if (res.ok) {
            const data = await res.json();
            if (data.ingestion_progress &&
              data.ingestion_progress.phase !== "complete" &&
              data.ingestion_progress.phase !== "failed") {
              setIngestionProgress(data.ingestion_progress);
              startProgressStream(sessionId);
            }
          }
        } catch (err) {
          console.error("Failed to fetch session progress:", err);
        }
      };

      fetchSessionProgress();
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
    // Note: STREAM_URL is already defined in ChatPanel, but I'll use relative or absolute here
    const sseUrl = `http://127.0.0.1:5328/ingest-progress/${id}`;
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

  return (
    <>
      <h2>Document Hub</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "16px" }}>
        Upload PDF or text files to build the agent&apos;s knowledge base.
      </p>

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
      )}

      {uploadStatus && !ingestionProgress && (
        <div style={{ padding: "12px", background: "var(--sys-msg-bg)", borderRadius: "8px", fontSize: "0.9rem", marginTop: "16px" }}>
          {uploadStatus}
        </div>
      )}
    </>
  );
}
