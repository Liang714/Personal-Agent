import { useState } from "react";
import "./App.css";
import ChatPanel from "./components/ChatPanel";
import InboxPanel from "./components/InboxPanel";
import CalendarPanel from "./components/CalendarPanel";
import MemoPanel from "./components/MemoPanel";

type Tab = "chat" | "inbox" | "calendar" | "memo";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "inbox", label: "Inbox" },
  { id: "calendar", label: "Calendar" },
  { id: "memo", label: "Memo" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="app">
      <header className="app-header">
        <h1>Personal Agent</h1>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "tab--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {tab === "chat" && <ChatPanel />}
        {tab === "inbox" && <InboxPanel />}
        {tab === "calendar" && <CalendarPanel />}
        {tab === "memo" && <MemoPanel />}
      </main>
    </div>
  );
}
