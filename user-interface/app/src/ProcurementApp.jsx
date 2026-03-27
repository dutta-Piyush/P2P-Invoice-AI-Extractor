import { useState } from "react";
import IntakeForm from "./components/IntakeForm";
import RequestOverview from "./components/RequestOverview";
import "./ProcurementApp.css";

export default function ProcurementApp() {
  const [view, setView] = useState("intake");
  const [refreshKey, setRefreshKey] = useState(0);
  const [notice, setNotice] = useState({ text: "", type: "" });

  const showNotice = (text) => setNotice({ text, type: "success" });
  const showError = (text) => setNotice({ text, type: "error" });
  const dismissNotice = () => setNotice({ text: "", type: "" });

  const handleSubmitted = (message) => {
    setRefreshKey((k) => k + 1);
    showNotice(message || "Request submitted.");
    setView("overview");
  };

  return (
    <div className="container">
      <header className="header">
        <h1>Procurement Requests &nbsp;&nbsp;</h1>
        <div className="tabs">
          <button
            className={view === "intake" ? "tab active" : "tab"}
            onClick={() => setView("intake")}
          >
            New request
          </button>
          <button
            className={view === "overview" ? "tab active" : "tab"}
            onClick={() => setView("overview")}
          >
            Request overview
          </button>
        </div>
      </header>

      {notice.text && (
        <div className={`notice notice-${notice.type}`}>
          <span>{notice.text}</span>
          <button
            className="notice-close"
            onClick={dismissNotice}
            aria-label="Dismiss"
          >
            &times;
          </button>
        </div>
      )}

      <main>
        {view === "intake" ? (
          <IntakeForm
            onSubmit={handleSubmitted}
            onNotice={showNotice}
            onError={showError}
          />
        ) : (
          <RequestOverview refreshKey={refreshKey} onNotice={showNotice} />
        )}
      </main>
    </div>
  );
}
