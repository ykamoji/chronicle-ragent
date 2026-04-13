"use client";
import { SessionProvider, useSession } from "../../context/SessionContext";
import Sidebar from "../../components/Sidebar";
import ChatPanel from "../../components/ChatPanel";
import IngestionPanel from "../../components/IngestionPanel";

function ChatLayout() {
  const { isPanelExpanded } = useSession();

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

export default function ChatPage() {
  return (
    <SessionProvider>
      <ChatLayout />
    </SessionProvider>
  );
}
