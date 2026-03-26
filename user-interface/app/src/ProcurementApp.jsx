import { useState } from "react";
import IntakeForm from "./components/IntakeForm";
import RequestOverview from "./components/RequestOverview";
import "./ProcurementApp.css";

export default function ProcurementApp() {
  const [view, setView] = useState("intake");
  const [refreshKey, setRefreshKey] = useState(0);
  const [notice, setNotice] = useState("");

  const handleSubmitted = (message) => {
    setRefreshKey((k) => k + 1);
    setNotice(message || "Request submitted.");
    setView("overview");
  };

  return (
    <div className="container">
      <header className="header">
        <h1>Procurement Requests</h1>
        <div className="tabs">
          <button className={view === "intake" ? "tab active" : "tab"} onClick={() => setView("intake")}>
            New request
          </button>
          <button className={view === "overview" ? "tab active" : "tab"} onClick={() => setView("overview")}>
            Request overview
          </button>
        </div>
      </header>

      {notice && (
        <div className="notice" onClick={() => setNotice("")}>
          {notice}
        </div>
      )}

      <main>
        {view === "intake" ? (
          <IntakeForm onSubmit={handleSubmitted} onNotice={setNotice} />
        ) : (
          <RequestOverview refreshKey={refreshKey} onNotice={setNotice} />
        )}
      </main>
    </div>
  );
}
