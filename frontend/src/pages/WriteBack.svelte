<script>
  import { currentProject } from '../stores/project.js';
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';

  let preview = $state(null);
  let result = $state(null);
  let loading = $state('');

  async function loadPreview() {
    loading = 'preview';
    try {
      preview = await api.writebackPreview($currentProject.id);
    } catch (e) {
      notify(e.message, 'error');
    }
    loading = '';
  }

  async function runWriteback() {
    loading = 'writeback';
    result = null;
    try {
      result = await api.writeback($currentProject.id);
      notify(`Writeback hotov: ${result.replaced} textu nahrazeno`, 'success');
      const updated = await api.getProject($currentProject.id);
      currentProject.set(updated);
    } catch (e) {
      notify(e.message, 'error');
    }
    loading = '';
  }

  function downloadIdml() {
    if (!$currentProject?.exports?.idml_cz) return;
    window.open(`/api/projects/${$currentProject.id}/download/idml_cz`, '_blank');
  }

  $effect(() => {
    if ($currentProject?.type === 'idml' && $currentProject?.idml_path) {
      loadPreview();
    }
  });
</script>

<div class="max-w-2xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Zapis zpet</h1>

  {#if !$currentProject}
    <p class="text-gray-500">Zadny projekt neni otevren.</p>

  {:else if $currentProject.type === 'map'}
    <div class="bg-white rounded-xl border border-gray-200 p-8 text-center">
      <div class="text-4xl mb-4">&#x1F5FA;</div>
      <h2 class="text-lg font-semibold mb-2">MAP: Zapis do Illustratoru</h2>
      <p class="text-sm text-gray-500 mb-4">Zatim neimplementovano.</p>
    </div>

  {:else}
    {#if preview}
      <div class="bg-white rounded-lg border border-gray-200 p-4 mb-4">
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>Celkem elementu: <span class="font-semibold">{preview.total_elements}</span></div>
          <div>S prekladem: <span class="font-semibold text-green-700">{preview.with_translation}</span></div>
          <div>K zapisu: <span class="font-semibold text-blue-700">{preview.writable}</span></div>
          <div>Chybi preklad: <span class="font-semibold text-orange-600">{preview.missing_translation}</span></div>
        </div>
        <div class="mt-3 bg-gray-100 rounded-full h-2">
          <div class="bg-green-500 rounded-full h-2 transition-all" style="width: {preview.coverage_pct}%"></div>
        </div>
        <div class="text-xs text-gray-500 mt-1 text-right">{preview.coverage_pct}% pokryti</div>
      </div>
    {/if}

    <div class="bg-white rounded-xl border border-gray-200 p-6 text-center">
      {#if result}
        <div class="text-green-600 text-4xl mb-3">&#x2705;</div>
        <h2 class="text-lg font-semibold mb-2">IDML vytvoreno</h2>
        <p class="text-sm text-gray-600 mb-1">
          Nahrazeno: <span class="font-semibold">{result.replaced}</span> / {result.total_elements} textu
        </p>
        {#if result.errors?.length > 0}
          <p class="text-xs text-orange-600 mb-3">{result.errors.length} upozorneni</p>
        {/if}
        <div class="flex gap-3 justify-center mt-4">
          <button
            class="px-5 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            onclick={downloadIdml}
          >
            Stahnout CZ IDML
          </button>
          <button
            class="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
            onclick={() => { result = null; }}
          >
            Znovu
          </button>
        </div>
      {:else}
        <div class="text-4xl mb-4">&#x1F4F0;</div>
        <h2 class="text-lg font-semibold mb-2">IDML: Repack a stazeni</h2>
        <p class="text-sm text-gray-500 mb-4">
          Aplikuje ceske preklady do IDML a nabidne stahnuti lokalizovaneho souboru.
        </p>
        <button
          class="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
          disabled={loading === 'writeback' || !preview || preview.writable === 0}
          onclick={runWriteback}
        >
          {loading === 'writeback' ? 'Vytvari se...' : 'Vytvorit CZ IDML'}
        </button>
      {/if}
    </div>
  {/if}
</div>
