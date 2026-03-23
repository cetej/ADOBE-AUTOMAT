import { writable, get } from 'svelte/store';
import { currentProject } from './project.js';

function parseHash() {
  const raw = window.location.hash.slice(1) || 'dashboard';
  // Oddelit query params (?style=xxx)
  const [pathPart, queryPart] = raw.split('?');
  const [pg, ...rest] = pathPart.split('/');

  // Query params
  const params = {};
  if (queryPart) {
    for (const pair of queryPart.split('&')) {
      const [k, v] = pair.split('=');
      if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || '');
    }
  }

  return {
    page: pg || 'dashboard',
    projectId: rest.join('/') || null,
    query: params,
  };
}

const initial = parseHash();
export const page = writable(initial.page);
export const pendingProjectId = writable(initial.projectId);
export const queryParams = writable(initial.query);

window.addEventListener('hashchange', () => {
  const { page: pg, projectId, query } = parseHash();
  page.set(pg);
  pendingProjectId.set(projectId);
  queryParams.set(query);
});

export function navigate(target) {
  const proj = get(currentProject);
  // layout-wizard, pattern-editor — projdi primo (muze mit vlastni projectId/query)
  if (target.startsWith('layout-wizard') || target.startsWith('pattern-editor')) {
    window.location.hash = target;
  } else if (proj && !target.includes('/')) {
    // Zachovat project ID v hashi
    window.location.hash = `${target}/${proj.id}`;
  } else {
    window.location.hash = target;
  }
  const { page: pg, projectId, query } = parseHash();
  page.set(pg);
  pendingProjectId.set(projectId);
  queryParams.set(query);
}

export function goHome() {
  window.location.hash = 'dashboard';
  page.set('dashboard');
  pendingProjectId.set(null);
  queryParams.set({});
}
