import { writable } from 'svelte/store';

/** Aktualni projekt. */
export const currentProject = writable(null);

/** Seznam vsech projektu. */
export const projectList = writable([]);

/** Aktualni stranka (hash routing). */
export const currentPage = writable(window.location.hash.slice(1) || 'dashboard');
