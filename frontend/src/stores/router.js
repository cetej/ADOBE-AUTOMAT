import { writable } from 'svelte/store';

export const page = writable(window.location.hash.slice(1) || 'dashboard');

window.addEventListener('hashchange', () => {
  page.set(window.location.hash.slice(1) || 'dashboard');
});

export function navigate(target) {
  window.location.hash = target;
  page.set(target);
}

export function goHome() {
  window.location.hash = 'dashboard';
  page.set('dashboard');
}
