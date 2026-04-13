"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import "./LandingPage.css";

export default function LandingPage() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  const features = [
    {
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="11" y1="8" x2="11" y2="14" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      ),
      title: "Semantic Search",
      desc: "Vector-powered retrieval finds relevant passages across your entire novel corpus instantly.",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a10 10 0 1 0 10 10" />
          <path d="M12 6v6l4 2" />
          <path d="M22 2l-5 5" />
          <path d="M17 2h5v5" />
        </svg>
      ),
      title: "ReAct Agent",
      desc: "An orchestrated reasoning loop thinks step-by-step, selecting the right tools to answer complex questions.",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
          <polyline points="7 10 10 13 13 10 16 13" />
        </svg>
      ),
      title: "Live Analytics",
      desc: "Track model performance, tool usage, and query latency across all sessions in real time.",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      ),
      title: "Document Hub",
      desc: "Upload PDFs or text files and watch the ingestion pipeline extract, embed, and index your content.",
    },
  ];

  const stats = [
    { value: "ReAct", label: "Agent Framework" },
    { value: "RAG", label: "Retrieval Method" },
    { value: "SSE", label: "Streaming Events" },
    { value: "Atlas MongoDB", label: "Vector Store" },
  ];

  return (
    <div className={`landing-page ${visible ? "landing-visible" : ""}`}>
      {/* Animated background orbs */}
      <div className="landing-orb landing-orb-1" />
      <div className="landing-orb landing-orb-2" />
      <div className="landing-orb landing-orb-3" />

      {/* Top nav */}
      <nav className="landing-nav">
        <div className="landing-logo">
          <div className="landing-logo-dot" />
          <span>Chronicle</span>
          <div className="landing-logo-dot" />
          <span>Agentic RAG</span>
          {/* </div> */}
        </div>
        {/* <button className="landing-nav-link" onClick={() => router.push('/dashboard/analytics')}>
          Analytics
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="8" x2="13" y2="8" />
            <polyline points="9 4 13 8 9 12" />
          </svg>
        </button> */}
      </nav>

      {/* Hero section */}
      <section className="landing-hero">

        <h1 className="landing-title">
          Your Novel,
          <br />
          <span className="landing-title-gradient">Intelligently Answered</span>
        </h1>

        <p className="landing-subtitle">
          Chronicle combines vector search with a ReAct reasoning agent to answer nuanced questions
          across your novel — with full transparency into every step.
        </p>

        <div className="landing-cta-group">
          <button className="landing-cta-primary" onClick={() => router.push('/chat')}>
            <svg viewBox="0 0 20 20" width="18" height="18" fill="currentColor">
              <path d="M2 5a2 2 0 012-2h11a2 2 0 012 2v7a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
            </svg>
            Start Chating
          </button>
          <button className="landing-cta-secondary" onClick={() => router.push('/dashboard/analytics')}>
            <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="14" height="14" rx="2" />
              <path d="M7 13V9M10 13V7M13 13V11" />
            </svg>
            View Analytics
          </button>
        </div>

        {/* Stats strip */}
        <div className="landing-stats">
          {stats.map((s) => (
            <div key={s.label} className="landing-stat">
              <span className="landing-stat-value">{s.value}</span>
              <span className="landing-stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Feature cards */}
      <section className="landing-features">
        <p className="landing-section-label">What Chronicle does,</p>
        <div className="landing-feature-grid">
          {features.map((f) => (
            <div key={f.title} className="landing-feature-card">
              <div className="landing-feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Bottom CTA strip */}
      <div className="landing-bottom-cta">
        <span>Ready to explore your Novel?</span>
        <button className="landing-cta-primary" onClick={() => router.push('/chat')}>
          Open Dashboard →
        </button>
      </div>
    </div>
  );
}
