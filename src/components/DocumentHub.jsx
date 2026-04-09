"use client";
import { useState } from "react";
import { useSession } from "../context/SessionContext";
import "./DocumentHub.css";

const API_URL = "";

export default function DocumentHub() {
  const [uploadStatus, setUploadStatus] = useState("");
  const { sessionId, setSessionId } = useSession();

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus("Uploading...");
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
      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      setUploadStatus(`Ingesting ${file.name}...`);
    } catch (err) {
      console.error(err);
      setUploadStatus("Failed to upload.");
    }
  };

  return (
    <>
      <h2>Document Hub</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "16px" }}>
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

      {uploadStatus && (
        <div style={{ padding: "12px", background: "var(--sys-msg-bg)", borderRadius: "8px", fontSize: "0.9rem", marginTop: "16px" }}>
          {uploadStatus}
        </div>
      )}
    </>
  );
}
