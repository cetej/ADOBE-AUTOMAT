<script>
  import { currentProject } from '../stores/project.js';
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';

  let loading = $state('');

  async function exportCsv() {
    loading = 'csv';
    try {
      const res = await fetch(`/api/projects/${$currentProject.id}/export/csv`, { method: 'POST' });
      if (!res.ok) throw new Error('Export selhal');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${$currentProject.id}_translations.csv`;
      a.click();
      URL.revokeObjectURL(url);
      notify('CSV exportovan', 'success');
    } catch (e) {
      notify(e.message, 'error');
    }
    loading = '';
  }

  async function exportJson() {
    loading = 'json';
    try {
      const data = await api.exportFile($currentProject.id, 'json');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${$currentProject.id}_translations.json`;
      a.click();
      URL.revokeObjectURL(url);
      notify(`JSON: ${data.total} prekladu`, 'success');
    } catch (e) {
      notify(e.message, 'error');
    }
    loading = '';
  }
</script>

<div class="max-w-2xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Vystupy</h1>

  {#if !$currentProject}
    <p class="text-gray-500">Zadny projekt neni otevren.</p>
  {:else}
    {@const total = $currentProject.elements?.length || 0}
    {@const translated = $currentProject.elements?.filter(e => e.czech).length || 0}

    <div class="bg-white rounded-lg border border-gray-200 p-4 mb-4">
      <div class="text-sm text-gray-600">
        Preklady: <span class="font-semibold">{translated}/{total}</span>
        ({total > 0 ? Math.round(translated / total * 100) : 0}%)
      </div>
    </div>

    <div class="space-y-3">
      <div class="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between">
        <div>
          <div class="font-medium text-gray-900 text-sm">CSV tabulka</div>
          <div class="text-xs text-gray-500">Original | Cesky | Status | Kategorie</div>
        </div>
        <button
          class="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
          disabled={loading === 'csv' || translated === 0}
          onclick={exportCsv}
        >
          {loading === 'csv' ? 'Stahuji...' : 'Stahnout CSV'}
        </button>
      </div>

      <div class="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between">
        <div>
          <div class="font-medium text-gray-900 text-sm">JSON export</div>
          <div class="text-xs text-gray-500">Pro dalsi zpracovani, API, pipeline</div>
        </div>
        <button
          class="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
          disabled={loading === 'json' || translated === 0}
          onclick={exportJson}
        >
          {loading === 'json' ? 'Stahuji...' : 'Stahnout JSON'}
        </button>
      </div>
    </div>
  {/if}
</div>
