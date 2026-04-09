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
        </div>
    );
};
