"use client";
import "./globals.css";
import { SessionProvider, useSession } from "../context/SessionContext";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import IngestionPanel from "../components/IngestionPanel";
import AnalyticsDashboard from "../components/AnalyticsDashboard";

function AppLayout() {
  const { ingestionProgress, isPanelExpanded, showAnalytics, setShowAnalytics } = useSession();

  if (showAnalytics) {
    return <AnalyticsDashboard onClose={() => setShowAnalytics(false)} />;
  }

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
