import { writable } from 'svelte/store';

/** Aktualni projekt. */
export const currentProject = writable(null);

/** Seznam vsech projektu. */
export const projectList = writable([]);

// currentPage store odstranen — routing ridi $state v App.svelte + hashchange
