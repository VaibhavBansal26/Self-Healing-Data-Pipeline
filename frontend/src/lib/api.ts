export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json();
}

export async function safeGet<T>(path:string, fallback:T, errors:string[]): Promise<T>{
  try { return await apiGet<T>(path); }
  catch(e:any){ errors.push(e?.message || String(e)); return fallback; }
}
