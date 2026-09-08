import type { ValuationRequest, ValuationResponse } from "../types/valuation";

const API_BASE_URL = "https://valuation-copilot-api.onrender.com";
//const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export function createValuation(payload: ValuationRequest): Promise<ValuationResponse> {
  return request("/api/valuations", { method: "POST", body: JSON.stringify(payload) });
}

export function getValuation(id: string): Promise<ValuationResponse> {
  return request(`/api/valuations/${id}`);
}

export function listReviewQueue(): Promise<ValuationResponse[]> {
  return request("/api/review-queue");
}

export function submitReviewDecision(
  id: string,
  approved: boolean,
  analystOverridePsf?: number,
): Promise<{ status: string }> {
  return request(`/api/review-queue/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ approved, analyst_override_psf: analystOverridePsf ?? null }),
  });
}
