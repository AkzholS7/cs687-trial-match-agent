// api.js: all calls from the React app to the Flask backend (REST, JSON).
async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (HTTP ${res.status})`);
  return data;
}

export const api = {
  health: () => request('GET', '/api/health'),
  examples: () => request('GET', '/api/examples'),
  collections: () => request('GET', '/api/collections'),
  defaults: () => request('GET', '/api/settings/defaults'),
  trials: (collection, q = '', offset = 0, limit = 20) =>
    request('GET', `/api/trials?${new URLSearchParams({ collection, q, offset, limit })}`),
  trial: (collection, id) => request('GET', `/api/trials/${encodeURIComponent(collection)}/${encodeURIComponent(id)}`),
  match: (payload) => request('POST', '/api/match', payload),
  runs: () => request('GET', '/api/runs'),
  run: (id) => request('GET', `/api/runs/${id}`),
  deleteRun: (id) => request('DELETE', `/api/runs/${id}`),
  decide: (runId, trialId, decision, note = '') =>
    request('PUT', `/api/runs/${runId}/decisions/${encodeURIComponent(trialId)}`, { decision, note }),
  undecide: (runId, trialId) => request('DELETE', `/api/runs/${runId}/decisions/${encodeURIComponent(trialId)}`),
  stats: () => request('GET', '/api/stats'),
  benchmark: () => request('GET', '/api/benchmark'),
};
