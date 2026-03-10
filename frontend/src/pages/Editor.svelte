<script>
  import { currentProject } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { api } from '../lib/api.js';
  import StatusBadge from '../components/StatusBadge.svelte';
  import CategorySelect from '../components/CategorySelect.svelte';
  import FilterToolbar from '../components/FilterToolbar.svelte';
  import StatsPanel from '../components/StatsPanel.svelte';

  let search = $state('');
  let filterLayer = $state('');
  let filterCategory = $state('');
  let filterStatus = $state('');
  let editingId = $state(null);
  let editCzech = $state('');
  let editNotes = $state('');
  let saving = $state(false);
  let translating = $state(false);
  let translateProgress = $state('');
  let uploadingTranslation = $state(false);
  let dragOverTranslation = $state(false);

  // Unikatni vrstvy, kategorie, statusy pro filtry
  let layers = $derived([...new Set(($currentProject?.elements || []).map(e => e.layer_name).filter(Boolean))].sort());
  let categories = $derived([...new Set(($currentProject?.elements || []).map(e => e.category).filter(Boolean))].sort());
  let statuses = $derived([...new Set(($currentProject?.elements || []).map(e => e.status).filter(Boolean))]);

  // Filtrovane elementy
  let filtered = $derived.by(() => {
    let els = $currentProject?.elements || [];
    if (search) {
      const q = search.toLowerCase();
      els = els.filter(e =>
        e.contents.toLowerCase().includes(q) ||
        (e.czech || '').toLowerCase().includes(q) ||
        (e.layer_name || '').toLowerCase().includes(q)
      );
    }
    if (filterLayer) els = els.filter(e => e.layer_name === filterLayer);
    if (filterCategory) els = els.filter(e => e.category === filterCategory);
    if (filterStatus === '__none__') els = els.filter(e => !e.status);
    else if (filterStatus) els = els.filter(e => e.status === filterStatus);
    return els;
  });

  function startEdit(el) {
    editingId = el.id;
    editCzech = el.czech || '';
    editNotes = el.notes || '';
  }

  function cancelEdit() {
    editingId = null;
  }

  async function saveEdit(el) {
    if (!$currentProject) return;
    saving = true;
    try {
      const result = await api.updateText($currentProject.id, el.id, {
        czech: editCzech,
        notes: editNotes || null,
      });
      // Aktualizovat lokalne
      const idx = $currentProject.elements.findIndex(e => e.id === el.id);
      if (idx >= 0) {
        $currentProject.elements[idx] = { ...$currentProject.elements[idx], ...result };
        currentProject.set($currentProject);
      }
      editingId = null;
    } catch (e) {
      notify('Chyba ukladani: ' + e.message, 'error');
    } finally {
      saving = false;
    }
  }

  async function setStatus(el, status) {
    if (!$currentProject) return;
    try {
      const result = await api.updateText($currentProject.id, el.id, { status });
      const idx = $currentProject.elements.findIndex(e => e.id === el.id);
      if (idx >= 0) {
        $currentProject.elements[idx] = { ...$currentProject.elements[idx], ...result };
        currentProject.set($currentProject);
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  async function setCategory(el, category) {
    if (!$currentProject) return;
    try {
      const result = await api.updateText($currentProject.id, el.id, { category });
      const idx = $currentProject.elements.findIndex(e => e.id === el.id);
      if (idx >= 0) {
        $currentProject.elements[idx] = { ...$currentProject.elements[idx], ...result };
        currentProject.set($currentProject);
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  async function translateAll(overwrite = false) {
    if (!$currentProject) return;
    translating = true;
    const untranslated = $currentProject.elements.filter(e => !e.czech && e.contents.trim()).length;
    translateProgress = overwrite ? 'Prekladam vsechny...' : `Prekladam ${untranslated} neprelozených...`;
    try {
      const result = await api.translate($currentProject.id, { overwrite });
      if (result.project) {
        currentProject.set(result.project);
      }
      notify(`Prelozeno ${result.translated} textu`, 'success');
    } catch (e) {
      notify('Chyba prekladu: ' + e.message, 'error');
    } finally {
      translating = false;
      translateProgress = '';
    }
  }

  async function translateSelected() {
    if (!$currentProject) return;
    const ids = filtered.filter(e => !e.czech && e.contents.trim()).map(e => e.id);
    if (!ids.length) {
      notify('Zadne neprelozene texty ve filtru', 'warning');
      return;
    }
    translating = true;
    translateProgress = `Prekladam ${ids.length} filtrovaných...`;
    try {
      const result = await api.translate($currentProject.id, { ids });
      if (result.project) {
        currentProject.set(result.project);
      }
      notify(`Prelozeno ${result.translated} textu`, 'success');
    } catch (e) {
      notify('Chyba prekladu: ' + e.message, 'error');
    } finally {
      translating = false;
      translateProgress = '';
    }
  }

  async function saveTM() {
    if (!$currentProject) return;
    try {
      const result = await api.saveTM($currentProject.id);
      notify(`Translation memory: +${result.added} (celkem ${result.total})`, 'success');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  // === Nahrani prekladu (DOCX) ===
  function isTranslationFile(file) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    return ['docx', 'doc', 'txt', 'rtf'].includes(ext);
  }

  async function uploadTranslationFile(file) {
    if (!$currentProject || !isTranslationFile(file)) {
      notify('Nepodporovany format. Pouzijte .docx, .doc, .txt nebo .rtf', 'error');
      return;
    }
    uploadingTranslation = true;
    try {
      const result = await api.uploadTranslation($currentProject.id, file);
      currentProject.set(result);
      const matched = result.elements?.filter(e => e.czech)?.length || 0;
      notify(`Preklad nahran: ${matched} textu sparovano z ${file.name}`, 'success');
    } catch (e) {
      notify('Chyba nahrani prekladu: ' + e.message, 'error');
    } finally {
      uploadingTranslation = false;
    }
  }

  function handleTranslationDrop(e) {
    e.preventDefault();
    dragOverTranslation = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) uploadTranslationFile(file);
  }

  function handleTranslationSelect(e) {
    const file = e.target.files?.[0];
    if (file) uploadTranslationFile(file);
  }

  function handleKeydown(e, el) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      saveEdit(el);
    } else if (e.key === 'Escape') {
      cancelEdit();
    }
  }
</script>

<div class="flex gap-6 max-w-[1600px] mx-auto">
  <!-- Hlavni tabulka -->
  <div class="flex-1 min-w-0">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-gray-900">Prekladovy editor</h1>
      <div class="flex items-center gap-2">
        {#if translating}
          <span class="text-sm text-blue-600 animate-pulse">{translateProgress}</span>
        {:else}
          <button
            onclick={() => translateAll(false)}
            class="px-3 py-1.5 text-xs font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
          >AI Preklad</button>
          <button
            onclick={translateSelected}
            class="px-3 py-1.5 text-xs font-medium bg-violet-100 text-violet-700 rounded-lg hover:bg-violet-200 transition-colors"
          >Prelozit filtr</button>
          <button
            onclick={saveTM}
            class="px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors"
            title="Ulozit potvrzene preklady (OK) do translation memory"
          >Ulozit TM</button>
        {/if}
        {#if filtered.length > 0}
          <span class="text-sm text-gray-500 ml-2">{filtered.length} / {$currentProject?.elements?.length || 0}</span>
        {/if}
      </div>
    </div>

    <!-- Panel prekladu — IDML bez prekladu -->
    {#if $currentProject?.type === 'idml' && $currentProject?.elements?.length > 0}
      {@const hasTranslations = $currentProject.elements.some(e => e.czech)}
      {#if !hasTranslations && !translating}
        <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
          <div class="flex items-center gap-4">
            <div class="flex-1">
              <p class="text-sm font-medium text-amber-800 mb-1">Texty nemaji preklad</p>
              <p class="text-xs text-amber-600">Nahrejte .docx preklad nebo spustte AI preklad</p>
            </div>
            <div class="flex items-center gap-2">
              <!-- Drop zone pro preklad -->
              {#if uploadingTranslation}
                <span class="text-xs text-blue-600 animate-pulse">Nahravam...</span>
              {:else}
                <div
                  class="relative"
                  ondragover={(e) => { e.preventDefault(); dragOverTranslation = true; }}
                  ondragleave={() => { dragOverTranslation = false; }}
                  ondrop={handleTranslationDrop}
                >
                  <label class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg cursor-pointer transition-colors
                    {dragOverTranslation ? 'bg-blue-200 text-blue-800 ring-2 ring-blue-400' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'}">
                    Nahrat .docx preklad
                    <input
                      type="file"
                      accept=".docx,.doc,.txt,.rtf"
                      onchange={handleTranslationSelect}
                      class="hidden"
                    />
                  </label>
                </div>
              {/if}
              <span class="text-xs text-gray-400">nebo</span>
              <button
                onclick={() => translateAll(false)}
                class="px-3 py-1.5 text-xs font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
              >AI Preklad</button>
            </div>
          </div>
        </div>
      {/if}
    {/if}

    {#if !$currentProject || !$currentProject.elements?.length}
      <div class="text-center py-16 text-gray-500">
        <p class="text-lg">Zadne texty k editaci</p>
        <p class="text-sm mt-1">Nejdriv spustte extrakci.</p>
      </div>
    {:else}
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <FilterToolbar
          bind:search
          bind:filterLayer
          bind:filterCategory
          bind:filterStatus
          {layers}
          {categories}
          {statuses}
        />

        <div class="overflow-x-auto max-h-[calc(100vh-220px)] overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-10">#</th>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-28">Vrstva</th>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Original</th>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cesky preklad</th>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-24">Kategorie</th>
                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-24">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              {#each filtered as el, i (el.id + '/' + i)}
                <tr
                  class="hover:bg-blue-50/40 transition-colors {editingId === el.id ? 'bg-blue-50' : ''}"
                >
                  <td class="px-3 py-2 text-gray-400 text-xs">{i + 1}</td>
                  <td class="px-3 py-2 text-gray-500 text-xs truncate max-w-[120px]" title={el.layer_name || ''}>
                    {el.layer_name || el.story_id || ''}
                  </td>
                  <td class="px-3 py-2 text-gray-900 font-mono text-xs">
                    {el.contents}
                    {#if el.fontSize}
                      <span class="text-gray-400 ml-1" title="Font size">{el.fontSize}pt</span>
                    {/if}
                  </td>
                  <td class="px-3 py-2">
                    {#if editingId === el.id}
                      <div class="flex flex-col gap-1">
                        <input
                          type="text"
                          bind:value={editCzech}
                          onkeydown={(e) => handleKeydown(e, el)}
                          class="w-full border border-blue-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                          placeholder="Cesky preklad..."
                        />
                        <input
                          type="text"
                          bind:value={editNotes}
                          onkeydown={(e) => handleKeydown(e, el)}
                          class="w-full border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-300"
                          placeholder="Poznamka (volitelne)"
                        />
                        <div class="flex gap-1">
                          <button
                            onclick={() => saveEdit(el)}
                            disabled={saving}
                            class="px-2 py-0.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                          >Ulozit</button>
                          <button
                            onclick={cancelEdit}
                            class="px-2 py-0.5 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                          >Zrusit</button>
                        </div>
                      </div>
                    {:else}
                      <button
                        class="text-left w-full group cursor-text"
                        ondblclick={() => startEdit(el)}
                        title="Dvojklik pro editaci"
                      >
                        {#if el.czech}
                          <span class="text-blue-700 text-sm">{el.czech}</span>
                        {:else}
                          <span class="text-gray-300 text-sm group-hover:text-gray-400 italic">dvojklik pro editaci</span>
                        {/if}
                        {#if el.notes}
                          <span class="block text-xs text-gray-400 mt-0.5">{el.notes}</span>
                        {/if}
                      </button>
                    {/if}
                  </td>
                  <td class="px-3 py-2">
                    <CategorySelect
                      value={el.category}
                      compact={true}
                      projectType={$currentProject?.type || 'map'}
                      onchange={(e) => setCategory(el, e.target.value || null)}
                    />
                  </td>
                  <td class="px-3 py-2">
                    <select
                      value={el.status || ''}
                      onchange={(e) => setStatus(el, e.target.value || null)}
                      class="text-xs border border-gray-200 rounded px-1.5 py-0.5 bg-white w-20 focus:outline-none focus:ring-1 focus:ring-blue-400"
                    >
                      <option value="">--</option>
                      <option value="OK">OK</option>
                      <option value="OPRAVIT">OPRAVIT</option>
                      <option value="OVERIT">OVERIT</option>
                      <option value="PREVZIT">PREVZIT</option>
                      <option value="CHYBI">CHYBI</option>
                    </select>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  </div>

  <!-- Sidebar statistiky -->
  {#if $currentProject?.elements?.length}
    <div class="w-56 flex-shrink-0">
      <StatsPanel elements={$currentProject.elements} />
    </div>
  {/if}
</div>
