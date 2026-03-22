import { writable, get } from 'svelte/store';
import { currentProject } from './project.js';

function parseHash() {
  const raw = window.location.hash.slice(1) || 'dashboard';
  const [pg, ...rest] = raw.split('/');
  return { page: pg || 'dashboard', projectId: rest.join('/') || null };
}

const initial = parseHash();
export const page = writable(initial.page);
export const pendingProjectId = writable(initial.projectId);

window.addEventListener('hashchange', () => {
  const { page: pg, projectId } = parseHash();
  page.set(pg);
  pendingProjectId.set(projectId);
});

export function navigate(target) {
  const proj = get(currentProject);
  // Zachovat project ID v hashi
  if (proj && !target.includes('/')) {
    window.location.hash = `${target}/${proj.id}`;
  } else {
    window.location.hash = target;
  }
  const { page: pg, projectId } = parseHash();
  page.set(pg);
  pendingProjectId.set(projectId);
}

export function goHome() {
  window.location.hash = 'dashboard';
  page.set('dashboard');
  pendingProjectId.set(null);
}
