import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getHealth } from "./api/client";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { ValuationRequestPage } from "./pages/ValuationRequestPage";
import { ValuationResultPage } from "./pages/ValuationResultPage";

function App() {
  const [backendStatus, setBackendStatus] = useState("checking...");

  useEffect(() => {
    getHealth()
      .then((res) => setBackendStatus(res.status))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  return (
    <div>
      <header>
        <h1>Autonomous Valuation & Market Intelligence Copilot</h1>
        <p>Backend status: {backendStatus}</p>
        <nav>
          <NavLink to="/">New Valuation</NavLink>
          {" | "}
          <NavLink to="/review-queue">Review Queue</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<ValuationRequestPage />} />
          <Route path="/valuations/:id" element={<ValuationResultPage />} />
          <Route path="/review-queue" element={<ReviewQueuePage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
