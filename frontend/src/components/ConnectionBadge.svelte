<script>
  import { connectionStatus } from '../stores/connection.js';
  import { api } from '../lib/api.js';

  let status = $state({ connected: false, checking: true, error: null });
  connectionStatus.subscribe(v => status = v);

  async function checkConnection() {
    connectionStatus.set({ connected: false, checking: true, error: null });
    try {
      const result = await api.illustratorStatus();
      connectionStatus.set({
        connected: result.connected,
        checking: false,
        error: result.connected ? null : (result.error || 'Not connected'),
      });
    } catch (e) {
      connectionStatus.set({ connected: false, checking: false, error: e.message });
    }
  }

  checkConnection();
  $effect(() => {
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  });
</script>

<button
  class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border border-gray-200 hover:bg-gray-50 transition-colors"
  onclick={checkConnection}
  title={status.error || 'Illustrator connection'}
>
  {#if status.checking}
    <span class="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse"></span>
    <span class="text-gray-600">Checking...</span>
  {:else if status.connected}
    <span class="w-2.5 h-2.5 rounded-full bg-green-500"></span>
    <span class="text-green-700">Illustrator</span>
  {:else}
    <span class="w-2.5 h-2.5 rounded-full bg-red-500"></span>
    <span class="text-red-700">Offline</span>
  {/if}
</button>
