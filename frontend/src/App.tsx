import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getHealth } from "./api/client";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { ValuationRequestPage } from "./pages/ValuationRequestPage";
import { ValuationResultPage } from "./pages/ValuationResultPage";

type BackendState = "pending" | "ok" | "error";

function App() {
  const [backendState, setBackendState] = useState<BackendState>("pending");

  useEffect(() => {
    getHealth()
      .then(() => setBackendState("ok"))
      .catch(() => setBackendState("error"));
  }, []);

  const statusLabel =
    backendState === "ok" ? "Backend connected" : backendState === "error" ? "Backend unreachable" : "Connecting…";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">AV</span>
          <div className="brand-text">
            <span className="brand-title">
              From data to deal in seconds: Instant, autonomous valuations and real-time market insights
            </span>
            <span className="brand-subtitle">Newmark evidence-grounded rent recommendations</span>
          </div>
        </div>

        <nav className="topbar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-pill${isActive ? " active" : ""}`}>
            New Valuation
          </NavLink>
          <NavLink to="/review-queue" className={({ isActive }) => `nav-pill${isActive ? " active" : ""}`}>
            Review Queue
          </NavLink>
        </nav>

        <span className="status-pill" data-state={backendState}>
          <span className="status-dot" />
          {statusLabel}
        </span>
      </header>

      <main className="app-main">
        <div className="container">
          <Routes>
            <Route path="/" element={<ValuationRequestPage />} />
            <Route path="/valuations/:id" element={<ValuationResultPage />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default App;
