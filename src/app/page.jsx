"use client";
import "./globals.css";
import { SessionProvider, useSession } from "../context/SessionContext";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import DocumentHub from "../components/DocumentHub";
import ChapterSummaries from "../components/ChapterSummaries";

function AppLayout() {
  const { currentSummaries } = useSession();

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <ChatPanel />

      <aside className="ingestion-panel glass-panel">
        {currentSummaries && currentSummaries.length > 0 ? (
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
