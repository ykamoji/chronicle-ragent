import { useEffect, useRef } from "react";
import { useSession } from "../context/SessionContext";
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
      <h2>Chapter Summaries</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {currentSummaries.map((item, idx) => {
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
              </div>
            </details>
          );
        })}
      </div>
    </>
  );
}
