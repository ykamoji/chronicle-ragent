"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import "./SettingsPanel.css";
import { API_URL } from "../../../api";

export default function SettingsPanel({ isCollapsed }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState(null);
  const [delayValue, setDelayValue] = useState("");
  const panelRef = useRef(null);

  // ── Fetch settings on mount ──

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setDelayValue(data.delayOverride != null ? String(data.delayOverride) : "");
      }
    } catch (err) {
      console.error("Failed to load settings", err);
    }
  };

  const updateSettings = async (patch) => {
    try {
      const res = await fetch(`${API_URL}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (err) {
      console.error("Failed to update settings", err);
    }
  };

  const handleModelSelect = (modelId, delay) => {
    updateSettings({ model: modelId, delayOverride: delay });
    setDelayValue(delay);
  };

  const handleDelayChange = (e) => {
    const raw = e.target.value;
    setDelayValue(raw);
  };

  const handleDelayBlur = () => {
    const parsed = delayValue.trim() === "" ? null : parseInt(delayValue, 10);
    if (parsed !== null && isNaN(parsed)) return; // ignore invalid
    updateSettings({ delayOverride: parsed });
  };

  const handleDelayKeyDown = (e) => {
    if (e.key === "Enter") {
      e.target.blur(); // triggers handleDelayBlur
    }
  };

  const handleDummyAction = (label) => {
    alert(`${label} — coming soon!`);
  };

  const activeModel = settings?.activeModel;
  const modelList = settings?.modelList || [];
  const effectiveDelay = settings?.delayOverride ?? activeModel?.delay ?? "—";

  return (
    <>
      {/* ── Sidebar footer (always visible) ── */}
      <div className={`settings-footer${isCollapsed ? " collapsed" : ""}`}>
        {activeModel && (
          <div className="settings-model-chip" onClick={() => setOpen(true)}>
            <span className="model-dot" />
            <span className="model-name">{activeModel.name}</span>
          </div>
        )}
        <button
          className="settings-trigger-btn"
          onClick={() => { setOpen(true); fetchSettings(); }}
        >
          <span>⚙</span>
          <span className="settings-label-text">Settings & Help</span>
        </button>
      </div>

      {/* ── Slide-up config overlay ── */}
      {open && (
        <div className="settings-overlay">
          <div className="settings-overlay-backdrop" onClick={() => setOpen(false)} />
          <div className="settings-panel" ref={panelRef}>
            {/* Header */}
            <div className="settings-panel-header">
              <h3>Settings</h3>
              <button className="settings-close-btn" onClick={() => setOpen(false)}>✕</button>
            </div>

            {/* Model selection */}
            <div className="settings-section-label">Model</div>
            <div className="model-list">
              {modelList.map((m) => (
                <div
                  key={m.model}
                  className={`model-option${activeModel?.model === m.model ? " active" : ""}`}
                  onClick={() => handleModelSelect(m.model, m.delay)}
                >
                  <div className="model-radio">
                    <div className="model-radio-dot" />
                  </div>
                  <div className="model-option-info">
                    <span className="model-option-name">{m.name}</span>
                    <span className="model-option-id">{m.model}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="settings-divider" />

            {/* Delay override */}
            <div className="settings-section-label">Rate limit delay</div>
            <div className="delay-input-row">
              <label>Delays (sec)</label>
              <input
                type="number"
                className="delay-input"
                min="0"
                step="5"
                placeholder={String(activeModel?.delay ?? 10)}
                value={delayValue}
                onChange={handleDelayChange}
                onBlur={handleDelayBlur}
                onKeyDown={handleDelayKeyDown}
              />
            </div>
            <div className="delay-hint">
              Effective: {effectiveDelay}s — used between orchestrator steps &amp; ingestion calls.
            </div>

            <div className="settings-divider" />

            {/* Dummy actions */}
            <div className="settings-action-list">
              <button className="settings-action-item" onClick={() => { router.push('/dashboard/analytics'); setOpen(false); }}>
                <span className="settings-action-icon" style={{ paddingTop: "4px" }}>
                  <svg
                    viewBox="0 0 24 24"
                    width={18}
                    height={18}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M3 12a9 9 0 1 0 3-6.7" />
                    <polyline points="3 3 3 9 9 9" />
                    <path d="M12 7v5l3 2" />
                  </svg>
                </span>
                Activity
              </button>
              <button className="settings-action-item" onClick={() => handleDummyAction("Help")}>
                <span className="settings-action-icon">?</span>
                Help
              </button>
              <button className="settings-action-item" onClick={() => handleDummyAction("Send feedback")}>
                <span className="settings-action-icon" style={{ fontSize: "24px" }}>✉</span>
                Send feedback
              </button>
              <button className="settings-action-item" onClick={() => handleDummyAction("Theme")}>
                <span className="settings-action-icon">◐</span>
                Theme
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
