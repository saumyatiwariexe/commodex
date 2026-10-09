import { useQuery } from "@tanstack/react-query";

const BASE_URL = "http://localhost:8000/api/v1";

export async function fetchSpread(pair: string, fromDate: string, toDate: string) {
  const res = await fetch(`${BASE_URL}/spread?pair=${pair}&from=${fromDate}&to=${toDate}`);
  if (!res.ok) throw new Error("Failed to fetch spread");
  const json = await res.json();
  return json.data;
}

export async function fetchSignals(asOf: string) {
  const res = await fetch(`${BASE_URL}/signals?as_of=${asOf}`);
  if (!res.ok) throw new Error("Failed to fetch signals");
  const json = await res.json();
  return json.data;
}

export async function fetchCurve(symbol: string, asOf: string) {
  const res = await fetch(`${BASE_URL}/curve?symbol=${symbol}&as_of=${asOf}`);
  if (!res.ok) throw new Error("Failed to fetch curve");
  const json = await res.json();
  return json.data;
}

export function useSpread(pair: string, fromDate: string, toDate: string) {
  return useQuery({
    queryKey: ["spread", pair, fromDate, toDate],
    queryFn: () => fetchSpread(pair, fromDate, toDate),
  });
}

export function useSignals(asOf: string) {
  return useQuery({
    queryKey: ["signals", asOf],
    queryFn: () => fetchSignals(asOf),
  });
}

export function useCurve(symbol: string, asOf: string) {
  return useQuery({
    queryKey: ["curve", symbol, asOf],
    queryFn: () => fetchCurve(symbol, asOf),
  });
}
