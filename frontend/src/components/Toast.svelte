<script>
  import { notifications, dismiss } from '../stores/notifications.js';

  const colors = {
    info: 'bg-blue-100 text-blue-800 border-blue-300',
    success: 'bg-green-100 text-green-800 border-green-300',
    error: 'bg-red-100 text-red-800 border-red-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  };
</script>

<div class="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
  {#each $notifications as n (n.id)}
    <button
      class="px-4 py-3 rounded-lg border shadow-sm text-sm text-left w-full {colors[n.type] || colors.info}"
      onclick={() => dismiss(n.id)}
    >
      {n.message}
    </button>
  {/each}
</div>
