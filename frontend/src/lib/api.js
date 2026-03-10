/** Fetch wrapper pro API volani. */

const BASE = '/api';

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => request('GET', '/health'),

  // Illustrator
  illustratorStatus: () => request('GET', '/illustrator/status'),
  illustratorDocuments: () => request('GET', '/illustrator/documents'),

  // Projects
  listProjects: () => request('GET', '/projects'),
  getProject: (id) => request('GET', `/projects/${id}`),
  createProject: (data) => request('POST', '/projects', data),
  deleteProject: (id) => request('DELETE', `/projects/${id}`),

  // Extract
  extract: (id) => request('POST', `/projects/${id}/extract`),

  // IDML Upload (multipart — cannot use request() wrapper)
  uploadIdml: async (id, file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/projects/${id}/upload-idml`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
  uploadTranslation: async (id, file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/projects/${id}/upload-translation`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Texts
  updateText: (projectId, textId, data) =>
    request('PUT', `/projects/${projectId}/texts/${encodeURIComponent(textId)}`, data),
  bulkUpdateTexts: (projectId, data) =>
    request('PATCH', `/projects/${projectId}/texts/bulk`, data),

  // Categorize
  categorize: (id) => request('POST', `/projects/${id}/categorize`),

  // Translate
  translate: (id, opts = {}) => request('POST', `/projects/${id}/translate`, opts),
  saveTM: (id) => request('POST', `/projects/${id}/translate/save-tm`),

  // Export
  exportFile: (id, format) => request('POST', `/projects/${id}/export/${format}`),

  // Writeback (IDML)
  writeback: (id) => request('POST', `/projects/${id}/writeback`),
  writebackPreview: (id) => request('POST', `/projects/${id}/writeback/preview`),

  // Writeback (MAP → Illustrator)
  writebackMap: (id) => request('POST', `/projects/${id}/writeback-map`),
  writebackMapPreview: (id) => request('POST', `/projects/${id}/writeback-map/preview`),
};
