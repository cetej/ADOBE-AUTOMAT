import { writable } from 'svelte/store';

/** Stav pripojeni k Illustratoru. */
export const connectionStatus = writable({
  connected: false,
  checking: false,
  error: null,
});
