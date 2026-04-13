import { useSession } from "../../context/SessionContext";
import DocumentHub from "./DocumentHub/DocumentHub";
import ChapterSummaries from "./ChapterSummaries/ChapterSummaries";
import "./IngestionPanel.css";

export default function IngestionPanel() {
  const {
    currentSummaries,
    ingestionProgress,
    activeIngestionTab,
    setActiveIngestionTab,
    referenceText,
    isPanelExpanded,
    setIsPanelExpanded,
  } = useSession();

  const isIngesting =
    ingestionProgress &&
    ingestionProgress.phase !== "complete" &&
    ingestionProgress.phase !== "failed";

  const hasSummaries = currentSummaries && currentSummaries.length > 0 && !isIngesting;

  // Render tab content
  const renderContent = () => {
    switch (activeIngestionTab) {
      case "documents":
        return <DocumentHub />;
      case "summaries":
        return hasSummaries ? (
          <ChapterSummaries currentSummaries={currentSummaries} />
        ) : (
          <div className="empty-state">No summaries available yet. Upload a document to generate them.</div>
        );
      case "reference":
        return referenceText ? (
          <div className="reference-content">
            <h2>Reference Text</h2>
            <div className="reference-text-body">
              {referenceText.split('\n').map((para, i) => (
                para.trim() ? <p key={i}>{para}</p> : <br key={i} />
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">Click a specific text block in the chat to view the full reference document here.</div>
        );
      default:
        return <DocumentHub />;
    }
  };

  return (
    <div className="ingestion-panel-wrapper">
      <div className="panel-header">
        <button
          className="panel-toggle-btn"
          onClick={() => setIsPanelExpanded(!isPanelExpanded)}
          title={isPanelExpanded ? "Collapse Panel" : "Expand Panel"}
        >
          {isPanelExpanded ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 19l-7-7 7-7M19 19l-7-7 7-7" />
            </svg>
          )}
        </button>
      </div>

      <div style={{ display: isPanelExpanded ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
        <div className="tab-bar">
          <button
            className={`tab-item ${activeIngestionTab === "documents" ? "active" : ""}`}
            onClick={() => { setActiveIngestionTab("documents"); setIsPanelExpanded(true); }}
          >
            Documents
          </button>
          <button
            className={`tab-item ${activeIngestionTab === "summaries" ? "active" : ""}`}
            onClick={() => { setActiveIngestionTab("summaries"); setIsPanelExpanded(true); }}
            disabled={!hasSummaries && activeIngestionTab !== "summaries"}
          >
            Summaries
          </button>
          <button
            className={`tab-item ${activeIngestionTab === "reference" ? "active" : ""}`}
            onClick={() => { setActiveIngestionTab("reference"); setIsPanelExpanded(true); }}
            disabled={!referenceText && activeIngestionTab !== "reference"}
          >
            Reference
            {referenceText && <span className="tab-badge"></span>}
          </button>
        </div>

        <div className="tab-content">{renderContent()}</div>
      </div>
    </div>
  );
}
