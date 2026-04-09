"use client";
import { useState, useRef, useEffect } from "react";
import "./Observation.css";

export const CollapsibleObservation = ({ content }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isTruncated, setIsTruncated] = useState(false);
    const textRef = useRef(null);

    useEffect(() => {
        if (textRef.current && !isExpanded) {
            // Only check for truncation when collapsed to determine if toggle is needed
            const hasOverflow = textRef.current.scrollHeight > textRef.current.clientHeight;
            if (hasOverflow) {
                setIsTruncated(true);
            }
        }
    }, [content, isExpanded]);

    const extractSources = (text) => {
        if (!text) return [];
        const regex = /Source:\s*(Chapter\s*\d+)/gi;
        const matches = [...text.matchAll(regex)];
        // Extract the capture group (Chapter X) and uniqify
        return [...new Set(matches.map(m => m[1]))];
    };

    const sources = extractSources(content);

    return (
        <div className="observation-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
            <span
                ref={textRef}
                className={`step-text observation-text ${!isExpanded ? "collapsed" : ""}`}
            >
                {content}
            </span>
            {isTruncated && (
                <button
                    className="observation-toggle"
                    onClick={() => setIsExpanded(!isExpanded)}
                >
                    {isExpanded ? "Show Less" : "Read More"}
                </button>
            )}
            
            {sources.length > 0 && (
                <div className="sources-container">
                    <span className="sources-label">Sources:</span>
                    <div className="sources-list">
                        {sources.map((source, idx) => {
                            const linkId = source.toLowerCase().replace(/\s+/g, '-');
                            return (
                                <a 
                                    key={idx} 
                                    href={`#${linkId}`} 
                                    className="source-link"
                                >
                                    {source}
                                </a>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};
