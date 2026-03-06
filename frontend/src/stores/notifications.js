import { writable } from 'svelte/store';

/** Toast notifikace. */
export const notifications = writable([]);

let nextId = 0;

export function notify(message, type = 'info', duration = 4000) {
  const id = nextId++;
  notifications.update(n => [...n, { id, message, type }]);
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration);
  }
}

export function dismiss(id) {
  notifications.update(n => n.filter(x => x.id !== id));
}
