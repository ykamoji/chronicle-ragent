"use client";
import "./globals.css";
import { SessionProvider, useSession } from "../context/SessionContext";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import DocumentHub from "../components/DocumentHub";
import ChapterSummaries from "../components/ChapterSummaries";

function AppLayout() {
  const { currentSummaries, ingestionProgress } = useSession();

  const isIngesting = ingestionProgress &&
    ingestionProgress.phase !== "complete" &&
    ingestionProgress.phase !== "failed";

  const showSummaries = currentSummaries && currentSummaries.length > 0 && !isIngesting;

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <ChatPanel />

      <aside className="ingestion-panel glass-panel">
        {showSummaries ? (
          <ChapterSummaries currentSummaries={currentSummaries} />
        ) : (
          <DocumentHub />
        )}
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
