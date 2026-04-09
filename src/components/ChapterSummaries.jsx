import "./ChapterSummaries.css";

export default function ChapterSummaries({ currentSummaries }) {
  return (
    <>
      <h2>Chapter Summaries</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {currentSummaries.map((item, idx) => (
          <details 
            key={idx} 
            id={`${(item.chapter || `Chapter ${idx + 1}`).toString().toLowerCase().replace(/\s+/g, '-')}`}
            className="summary-card accordion"
          >
            <summary className="accordion-header">
              <span>{item.chapter !== "" ? item.chapter : `Chapter ${idx + 1}`}</span>
            </summary>
            <div className="accordion-content">
              <p style={{ marginTop: '8px', color: 'var(--text-secondary)' }}>
                {item.summary}
              </p>
            </div>
          </details>
        ))}
      </div>
    </>
  );
}
