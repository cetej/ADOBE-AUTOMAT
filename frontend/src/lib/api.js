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

  // Korektury
  correctionsManual: (id, entries) => request('POST', `/projects/${id}/corrections/manual`, { entries }),
  correctionsUpload: async (id, file) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/projects/${id}/corrections/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
  correctionsApply: (id, roundId) => request('POST', `/projects/${id}/corrections/${roundId}/apply`),
  correctionsList: (id) => request('GET', `/projects/${id}/corrections`),
  correctionsGet: (id, roundId) => request('GET', `/projects/${id}/corrections/${roundId}`),
  correctionsAi: (id, instruction) => request('POST', `/projects/${id}/corrections/ai`, { instruction }),
  correctionsAutoSuggestions: (id) => request('POST', `/projects/${id}/corrections/auto-suggestions`),

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
  layoutPlanDetail: (projectId, variant) => request('GET', `/layout/plan-detail/${projectId}${variant != null ? `?variant=${variant}` : ''}`),
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

  // Multi-Article (Session 10)
  layoutMultiUploadArticles: async (projectId, { text, files }) => {
    const fd = new FormData();
    if (text) fd.append('text', text);
    if (files) for (const f of files) fd.append('files', f);
    const res = await fetch(`${BASE}/layout/multi/upload-articles/${projectId}`, {
      method: 'POST', body: fd,
    });
    return res.json();
  },
  layoutMultiAllocateImages: (projectId, allocation) =>
    request('POST', `/layout/multi/allocate-images/${projectId}`, { allocation }),
  layoutMultiPlan: (projectId, opts = {}) =>
    request('POST', `/layout/multi/plan/${projectId}`, opts),
  layoutMultiPlanProgress: (projectId) =>
    request('GET', `/layout/multi/plan/${projectId}/progress`),
  layoutMultiGenerate: (projectId, opts = {}) =>
    request('POST', `/layout/multi/generate/${projectId}`, opts),
  layoutMultiGenerateProgress: (projectId) =>
    request('GET', `/layout/multi/generate/${projectId}/progress`),

  // Maps / Illustrator Integration (Session 11)
  layoutDetectMaps: (projectId, threshold = 0.3) =>
    request('POST', `/layout/detect-maps/${projectId}?threshold=${threshold}`),
  layoutExportMapTemplate: async (projectId, { slot_id, width, height, label_text, bleed }) => {
    const fd = new FormData();
    fd.append('slot_id', slot_id || 'map_0');
    fd.append('width', String(width || 400));
    fd.append('height', String(height || 400));
    fd.append('label_text', label_text || '');
    fd.append('bleed', String(bleed || 8.5));
    const res = await fetch(`${BASE}/layout/export-map-template/${projectId}`, {
      method: 'POST', body: fd,
    });
    return res.json();
  },
  layoutImportEditedMap: async (projectId, slotId, file) => {
    const fd = new FormData();
    fd.append('slot_id', slotId);
    fd.append('file', file);
    const res = await fetch(`${BASE}/layout/import-edited-map/${projectId}`, {
      method: 'POST', body: fd,
    });
    return res.json();
  },
  layoutListMaps: (projectId) => request('GET', `/layout/maps/${projectId}`),

  // Traces
  tracesSummary: (since = null, until = null, module = null) => {
    const params = new URLSearchParams();
    if (since) params.set('since', since);
    if (until) params.set('until', until);
    if (module) params.set('module', module);
    const qs = params.toString();
    return request('GET', `/traces/summary${qs ? '?' + qs : ''}`);
  },
  tracesRecent: (limit = 50) => request('GET', `/traces/recent?limit=${limit}`),
};
