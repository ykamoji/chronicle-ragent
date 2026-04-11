"use client";
import "./globals.css";
import { SessionProvider, useSession } from "../context/SessionContext";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import DocumentHub from "../components/DocumentHub";
import ChapterSummaries from "../components/ChapterSummaries";
import IngestionPanel from "../components/IngestionPanel";

function AppLayout() {
  const { currentSummaries, ingestionProgress, isPanelExpanded } = useSession();

  const isIngesting = ingestionProgress &&
    ingestionProgress.phase !== "complete" &&
    ingestionProgress.phase !== "failed";

  const showSummaries = currentSummaries && currentSummaries.length > 0 && !isIngesting;

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <ChatPanel />

      <aside className={`ingestion-panel glass-panel ${isPanelExpanded ? 'expanded' : 'collapsed'}`}>
        <IngestionPanel />
      </aside>
    </div>
  );
}

export default function Home() {
  return (
    <SessionProvider>
      <AppLayout />
    </SessionProvider>
  );
}
