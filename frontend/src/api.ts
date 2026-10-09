export const API_BASE_URL = "http://localhost:8000/api/v1";

export async function fetchContracts() {
  const res = await fetch(`${API_BASE_URL}/contracts`);
  if (!res.ok) throw new Error("Failed to fetch contracts");
  return res.json();
}

export async function fetchSignals(asOf: string) {
  const res = await fetch(`${API_BASE_URL}/signals?as_of=${asOf}`);
  if (!res.ok) throw new Error("Failed to fetch signals");
  return res.json();
}

export async function fetchSpread(pair: string) {
  const res = await fetch(`${API_BASE_URL}/spread?pair=${pair}`);
  if (!res.ok) throw new Error("Failed to fetch spread");
  return res.json();
}

export async function fetchCurve(symbol: string, asOf: string) {
  const res = await fetch(`${API_BASE_URL}/curve?symbol=${symbol}&as_of=${asOf}`);
  if (!res.ok) throw new Error("Failed to fetch curve");
  return res.json();
}
