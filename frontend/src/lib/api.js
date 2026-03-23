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

  uploadSourcePdf: async (id, file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/projects/${id}/upload-source-pdf`, {
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
  translateProgress: (id) => request('GET', `/projects/${id}/translate/progress`),
  saveTM: (id) => request('POST', `/projects/${id}/translate/save-tm`),

  // Text Pipeline — spuštění (vrátí okamžitě, běží na pozadí)
  processText: (id, opts = {}) => request('POST', `/projects/${id}/process-text`, opts),
  // Polling průběhu pipeline
  pipelineProgress: (id) => request('GET', `/projects/${id}/process-text/progress`),
  // Protokol změn
  pipelineChanges: (id) => request('GET', `/projects/${id}/pipeline-changes`),

  // Export
  exportFile: (id, format) => request('POST', `/projects/${id}/export/${format}`),

  // Writeback (IDML)
  writeback: (id) => request('POST', `/projects/${id}/writeback`),
  writebackPreview: (id) => request('POST', `/projects/${id}/writeback/preview`),

  // Writeback (MAP → Illustrator)
  writebackMap: (id) => request('POST', `/projects/${id}/writeback-map`),
  writebackMapPreview: (id) => request('POST', `/projects/${id}/writeback-map/preview`),

  // === Layout Generator ===
  layoutTemplates: () => request('GET', '/layout/templates'),
  layoutPatterns: () => request('GET', '/layout/patterns'),
  layoutListProjects: () => request('GET', '/layout/projects'),
  layoutGetProject: (id) => request('GET', `/layout/projects/${id}`),
  layoutCreateProject: (data) => request('POST', '/layout/create-project', data),
  layoutDeleteProject: (id) => request('DELETE', `/layout/projects/${id}`),

  layoutUploadImages: async (projectId, files) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    const res = await fetch(`${BASE}/layout/upload-images/${projectId}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  layoutUploadText: async (projectId, text) => {
    const form = new FormData();
    form.append('text', text);
    const res = await fetch(`${BASE}/layout/upload-text/${projectId}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  layoutUploadTextFile: async (projectId, file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/layout/upload-text/${projectId}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  layoutPlan: (projectId, opts = {}) => request('POST', `/layout/plan/${projectId}`, opts),
  layoutPlanProgress: (projectId) => request('GET', `/layout/plan/${projectId}/progress`),
  layoutGenerate: (projectId, opts = {}) => request('POST', `/layout/generate/${projectId}`, opts),
  layoutGenerateProgress: (projectId) => request('GET', `/layout/generate/${projectId}/progress`),
  layoutDownloadUrl: (projectId) => `${BASE}/layout/download/${projectId}`,

  // Session 7: Preview & Polish
  layoutThumbnailUrl: (projectId, filename, size = 200) =>
    `${BASE}/layout/thumbnail/${projectId}/${encodeURIComponent(filename)}?size=${size}`,
  layoutPlanDetail: (projectId) => request('GET', `/layout/plan-detail/${projectId}`),
  layoutUpdatePlan: (projectId, updates) => request('POST', `/layout/update-plan/${projectId}`, updates),
  layoutValidate: (projectId) => request('GET', `/layout/validate/${projectId}`),

  // Session 8: Pokročilé funkce
  // Style Transfer
  layoutCreateStyleFromTemplate: async (file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/layout/create-style-from-template`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
  layoutDeleteTemplate: (profileId) => request('DELETE', `/layout/templates/${profileId}`),

  // Batch generování
  layoutBatchPlan: (projectId, opts = {}) => request('POST', `/layout/batch-plan/${projectId}`, opts),
  layoutBatchGenerate: (projectId, opts = {}) => request('POST', `/layout/batch-generate/${projectId}`, opts),
  layoutBatchGenerateProgress: (projectId) => request('GET', `/layout/batch-generate/${projectId}/progress`),
  layoutBatchDownloadUrl: (projectId, variant) => `${BASE}/layout/batch-download/${projectId}/${variant}`,

  // PDF Preview
  layoutGeneratePreviewPdf: (projectId) => request('POST', `/layout/preview-pdf/${projectId}`),
  layoutPreviewPdfUrl: (projectId) => `${BASE}/layout/preview-pdf/${projectId}/download`,

  // Caption Matching
  layoutMatchCaptions: (projectId) => request('POST', `/layout/match-captions/${projectId}`),
  layoutMatchCaptionsProgress: (projectId) => request('GET', `/layout/match-captions/${projectId}/progress`),

  // Pattern Editor (Session 9)
  layoutPatternsDetail: () => request('GET', '/layout/patterns?detail=true'),
  layoutGetPattern: (id) => request('GET', `/layout/patterns/${id}`),
  layoutCreatePattern: (data) => request('POST', '/layout/patterns', data),
  layoutUpdatePattern: (id, data) => request('PUT', `/layout/patterns/${id}`, data),
  layoutDeletePattern: (id) => request('DELETE', `/layout/patterns/${id}`),
  layoutValidatePattern: (data) => request('POST', '/layout/patterns/validate', data),
};
