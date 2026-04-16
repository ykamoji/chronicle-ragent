import { useEffect, useRef } from "react";
import { useSession } from "../../../context/SessionContext";
import "./ChapterSummaries.css";

export default function ChapterSummaries({ currentSummaries }) {
  const { highlightChapter, setHighlightChapter } = useSession();
  const summaryRefs = useRef({});

  useEffect(() => {
    if (highlightChapter && summaryRefs.current[highlightChapter]) {
      for (const chapter in summaryRefs.current) {
        if (chapter !== highlightChapter && summaryRefs.current[chapter]) {
          summaryRefs.current[chapter].open = false;
        }
      }
      const el = summaryRefs.current[highlightChapter];
      el.open = true;

      setTimeout(() => {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    }
  }, [highlightChapter]);

  const handleToggle = (e) => {
    const current = e.target;
    if (current.open) {
      for (const chapter in summaryRefs.current) {
        if (current == summaryRefs.current[chapter]) {
          if (chapter == highlightChapter) {
            setHighlightChapter(null)
          }
          break
        }
      }
    }
  }

  return (
    <>
      <h2>Chapters <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>(summaries)</span></h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {currentSummaries?.map((item, idx) => {
          const chapterName = item.chapter !== "" ? item.chapter : `Chapter ${idx + 1}`;
          return (
            <details
              key={idx}
              id={`${chapterName.toString().toLowerCase().replace(/\s+/g, '-')}`}
              className="summary-card accordion"
              ref={(el) => (summaryRefs.current[chapterName] = el)}
              onToggle={handleToggle}
            >
              <summary className="accordion-header">
                <span>{chapterName}</span>
              </summary>
              <div className="accordion-content">
                <p style={{ marginTop: '8px', color: 'var(--text-secondary)' }}>
                  {item.summary}
                </p>
                {item.characters && item.characters.length > 0 && (
                  <div className="characters-badges" style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {item.characters.map((character, charIdx) => (
                      <span
                        key={charIdx}
                        className="character-badge"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '4px 10px',
                          backgroundColor: 'rgba(0, 0, 0, 0.08)',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '500',
                          color: 'var(--text-primary)',
                          border: '1px solid rgba(0, 0, 0, 0.12)',
                        }}
                      >
                        {character}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </>
  );
}
