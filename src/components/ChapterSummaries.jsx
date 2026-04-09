import "./ChapterSummaries.css";

export default function ChapterSummaries({ currentSummaries }) {
  return (
    <>
      <h2>Chapter Summaries</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {currentSummaries.map((summary, idx) => (
          <details key={idx} className="summary-card accordion">
            <summary className="accordion-header">
              <strong>Chapter {idx + 1}</strong>
            </summary>
            <div className="accordion-content">
              <p style={{ marginTop: '8px', color: 'var(--text-secondary)' }}>{summary}</p>
            </div>
          </details>
        ))}
      </div>
    </>
  );
}
