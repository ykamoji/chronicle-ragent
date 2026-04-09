"use client";
import "./ConfirmDialog.css";

export default function ConfirmDialog({ open, title, message, onConfirm, onCancel }) {
  if (!open) return null;

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-box" onClick={(e) => e.stopPropagation()}>
        <h3 className="dialog-title">{title || "Confirm"}</h3>
        <p className="dialog-message">{message || "Are you sure?"}</p>
        <div className="dialog-actions">
          <button className="dialog-btn cancel" onClick={onCancel}>
            Cancel
          </button>
          <button className="dialog-btn confirm" onClick={onConfirm}>
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
