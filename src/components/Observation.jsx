"use client";
import { useState } from "react";
import "./Observation.css";

export const CollapsibleObservation = ({ content }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const processContent = (text) => {
        if (!text) return [];
        // Split by [Source: Chapter X]
        const parts = text.split(/\[Source:\s*(Chapter\s*\d+)\]/gi);
        const blocks = [];

        for (let i = 1; i < parts.length; i += 2) {
            const source = parts[i];
            const rawText = (parts[i + 1] || "").trim();
            blocks.push({ source, text: rawText });
        }

        return blocks;
    };

    const blocks = processContent(content);

    console.log(content)
    console.log(blocks)

    const sources = [...new Set(blocks.map(b => b.source))];
    const showToggle = blocks.length > 0;

    return (
        <div className="observation-container">
            {sources.length > 0 && (
                <div className="sources-container">
                    <span className="sources-label">Sources:</span>
                    <div className="sources-list">
                        {sources.map((source, idx) => {
                            return (
                                <span key={idx} className="source-link">
                                    {source}
                                </span>
                            );
                        })}
                    </div>
                </div>
            )}

            {(isExpanded || !showToggle) && (
                <div className="observation-text-wrapper">
                    {blocks.length > 0 ? blocks.map((block, idx) => (
                        <div key={idx} className="observation-paragraph">
                            {block.source.length > 0 && <span className="source-header">[Source: {block.source}]</span>}
                            <p className="paragraph-text">{block.text}</p>
                        </div>
                    )) : <p className="paragraph-text">{content}</p>}
                </div>
            )}

            {showToggle && (
                <button
                    className="observation-toggle"
                    onClick={() => setIsExpanded(!isExpanded)}
                >
                    {isExpanded ? "Show Less" : "Read More"}
                </button>
            )}

        </div>
    );
};
