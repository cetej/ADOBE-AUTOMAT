<script>
  import { currentProject } from '../stores/project.js';
  import { api } from '../lib/api.js';

  let inputMode = $state('upload'); // 'upload' | 'manual' | 'ai'
  let loading = $state(false);
  let error = $state('');
  let success = '';

  // AI corrections state
  let aiInstruction = $state('');

  // Upload state
  let dragOver = $state(false);

  // Preview state
  let previewRoundId = $state(null);
  let previewEntries = $state([]);
  let previewStats = $state(null);
  let previewFile = $state('');

  // Manual corrections state
  let manualEdits = $state([]);

  // Historie
  let rounds = $state([]);
  let loadingRounds = $state(false);

  // Načti historii kol při mountu
  $effect(() => {
    if ($currentProject) {
      loadRounds();
    }
  });

  // Inicializuj manuální edity z elementů
  $effect(() => {
    if ($currentProject && inputMode === 'manual') {
      manualEdits = $currentProject.elements
        .filter(e => e.czech)
        .map(e => ({ element_id: e.id, before: e.czech, after: '', notes: '' }));
    }
  });

  async function loadRounds() {
    loadingRounds = true;
    try {
      const data = await api.correctionsList($currentProject.id);
      rounds = data.rounds || [];
    } catch (e) {
      console.error('Chyba načítání kol:', e);
    } finally {
      loadingRounds = false;
    }
  }

  // ─── Upload ─────────────────────────────────────────────

  function handleDragOver(e) {
    e.preventDefault();
    dragOver = true;
  }
  function handleDragLeave() {
    dragOver = false;
  }
  async function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) await uploadFile(file);
  }
  async function handleFileSelect(e) {
    const file = e.target?.files?.[0];
    if (file) await uploadFile(file);
  }

  async function uploadFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls', 'docx', 'pdf'].includes(ext)) {
      error = `Nepodporovaný typ souboru: .${ext}`;
      return;
    }

    loading = true;
    error = '';
    success = '';
    previewRoundId = null;
    previewEntries = [];

    try {
      const result = await api.correctionsUpload($currentProject.id, file);
      previewRoundId = result.round_id;
      previewEntries = result.entries || [];
      previewStats = result.stats;
      previewFile = result.source_file || file.name;
      success = `Načteno ${previewEntries.length} korektur ze souboru ${file.name}`;
    } catch (e) {
      error = e.message || 'Upload selhal';
    } finally {
      loading = false;
    }
  }

  // ─── Manual ─────────────────────────────────────────────

  async function submitManual() {
    const edited = manualEdits.filter(e => e.after.trim() && e.after !== e.before);
    if (!edited.length) {
      error = 'Žádné opravy k odeslání';
      return;
    }

    loading = true;
    error = '';
    success = '';
    try {
      const result = await api.correctionsManual($currentProject.id, edited);
      previewRoundId = result.round_id;
      previewEntries = result.entries || [];
      previewStats = result.stats;
      previewFile = 'ruční zadání';
      success = `Vytvořeno ${edited.length} korektur`;
    } catch (e) {
      error = e.message || 'Odeslání selhalo';
    } finally {
      loading = false;
    }
  }

  // ─── AI corrections ─────────────────────────────────────

  async function submitAi() {
    if (!aiInstruction.trim()) {
      error = 'Napište instrukci pro korektora';
      return;
    }

    loading = true;
    error = '';
    success = '';
    try {
      const result = await api.correctionsAi($currentProject.id, aiInstruction.trim());
      if (!result.round_id) {
        success = 'Žádné elementy nevyžadují změnu podle této instrukce.';
      } else {
        previewRoundId = result.round_id;
        previewEntries = result.entries || [];
        previewStats = result.stats;
        previewFile = result.source_file || `AI: ${aiInstruction.slice(0, 40)}`;
        success = `AI navrhuje ${previewEntries.length} oprav`;
      }
    } catch (e) {
      error = e.message || 'AI korekce selhaly';
    } finally {
      loading = false;
    }
  }

  // ─── Auto-suggestions (CzechCorrector) ─────────────────

  async function runAutoSuggestions() {
    loading = true;
    error = '';
    success = '';
    try {
      const result = await api.correctionsAutoSuggestions($currentProject.id);
      if (!result.round_id) {
        success = 'Korektor nenašel žádné problémy.';
      } else {
        previewRoundId = result.round_id;
        previewEntries = result.entries || [];
        previewStats = result.stats;
        previewFile = result.source_file || 'CzechCorrector (auto)';
        success = `Korektor navrhuje ${previewEntries.length} oprav (${result.stats?.typography || 0} typografie, ${result.stats?.suggestions || 0} jazykové)`;
      }
    } catch (e) {
      error = e.message || 'Auto-kontrola selhala';
    } finally {
      loading = false;
    }
  }

  // ─── Apply ──────────────────────────────────────────────

  async function applyRound() {
    if (!previewRoundId) return;

    loading = true;
    error = '';
    try {
      const result = await api.correctionsApply($currentProject.id, previewRoundId);
      success = `Kolo ${previewRoundId} aplikováno: ${result.stats?.applied || 0} oprav`;

      if (result.writeback?.output_path) {
        success += ` | Vytvořen verzovaný IDML`;
      }
      if (result.needs_map_writeback) {
        success += ' | Pro zápis do Illustratoru použijte záložku Zápis';
      }

      // Refresh
      previewRoundId = null;
      previewEntries = [];
      previewStats = null;
      await loadRounds();

      // Aktualizuj projekt v paměti
      const updated = await api.getProject($currentProject.id);
      currentProject.set(updated);
    } catch (e) {
      error = e.message || 'Aplikace selhala';
    } finally {
      loading = false;
    }
  }

  // ─── Download ───────────────────────────────────────────

  function downloadRound(roundId) {
    window.open(`/api/projects/${$currentProject.id}/corrections/${roundId}/download`, '_blank');
  }

  // ─── Helpers ────────────────────────────────────────────

  function confidenceColor(c) {
    if (c >= 0.95) return 'text-green-700 bg-green-50';
    if (c >= 0.85) return 'text-yellow-700 bg-yellow-50';
    return 'text-red-700 bg-red-50';
  }

  function confidenceLabel(c) {
    return `${Math.round(c * 100)} %`;
  }
</script>

{#if !$currentProject}
  <p class="text-gray-500 text-center py-16">Nejprve vyberte projekt.</p>
{:else}
  <div class="max-w-6xl mx-auto space-y-6">

    <!-- ─── Header ─────────────────────────────────── -->
    <div class="space-y-3">
      <h2 class="text-xl font-semibold text-gray-900">Korektury</h2>
      <div class="flex items-center gap-2">
        <button
          class="px-3 py-1.5 text-sm rounded-full transition-colors
                 {inputMode === 'upload' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
          onclick={() => { inputMode = 'upload'; previewRoundId = null; }}
        >
          Nahrát soubor
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded-full transition-colors
                 {inputMode === 'manual' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
          onclick={() => { inputMode = 'manual'; previewRoundId = null; }}
        >
          Ručně
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded-full transition-colors
                 {inputMode === 'ai' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
          onclick={() => { inputMode = 'ai'; previewRoundId = null; }}
        >
          AI korekce
        </button>
        <span class="border-l border-gray-300 h-5 mx-1"></span>
        <button
          class="px-3 py-1.5 text-sm rounded-full bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-50"
          onclick={runAutoSuggestions}
          disabled={loading}
        >
          {loading && inputMode !== 'ai' ? 'Analyzuji...' : 'Návrhy korektoru'}
        </button>
      </div>
    </div>

    <!-- ─── Messages ───────────────────────────────── -->
    {#if error}
      <div class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
        {error}
        <button class="ml-2 text-red-500 hover:text-red-700" onclick={() => error = ''}>x</button>
      </div>
    {/if}
    {#if success}
      <div class="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">
        {success}
        <button class="ml-2 text-green-500 hover:text-green-700" onclick={() => success = ''}>x</button>
      </div>
    {/if}

    <!-- ─── Upload mode ───────────────────────────── -->
    {#if inputMode === 'upload' && !previewRoundId}
      <div
        class="border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer
               {dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}"
        ondragover={handleDragOver}
        ondragleave={handleDragLeave}
        ondrop={handleDrop}
        onclick={() => document.getElementById('correction-file-input')?.click()}
        role="button"
        tabindex="0"
      >
        <input
          id="correction-file-input"
          type="file"
          accept=".xlsx,.xls,.docx,.pdf"
          onchange={handleFileSelect}
          class="hidden"
        />
        <div class="text-gray-500 space-y-2">
          <p class="text-lg font-medium">Přetáhněte soubor s korekturami</p>
          <p class="text-sm">nebo klikněte pro výběr</p>
          <p class="text-xs text-gray-400 mt-4">
            Podporované formáty: Excel (.xlsx), Word (.docx), PDF (.pdf)
          </p>
        </div>
      </div>
    {/if}

    <!-- ─── Manual mode ────────────────────────────── -->
    {#if inputMode === 'manual' && !previewRoundId}
      <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div class="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <span class="text-sm font-medium text-gray-700">Ruční korektury</span>
          <button
            class="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            onclick={submitManual}
            disabled={loading}
          >
            {loading ? 'Odesílám...' : 'Vytvořit kolo korektur'}
          </button>
        </div>
        <div class="overflow-x-auto max-h-[60vh] overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 sticky top-0">
              <tr>
                <th class="text-left px-3 py-2 text-gray-600 font-medium w-16">ID</th>
                <th class="text-left px-3 py-2 text-gray-600 font-medium">Aktuální text</th>
                <th class="text-left px-3 py-2 text-gray-600 font-medium">Oprava</th>
              </tr>
            </thead>
            <tbody>
              {#each manualEdits as edit, i}
                <tr class="border-t border-gray-100 hover:bg-gray-50">
                  <td class="px-3 py-2 text-xs text-gray-400 font-mono">{edit.element_id.slice(-12)}</td>
                  <td class="px-3 py-2 text-gray-700 max-w-xs truncate">{edit.before}</td>
                  <td class="px-3 py-2">
                    <input
                      type="text"
                      class="w-full px-2 py-1 border border-gray-200 rounded text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
                      placeholder="opravený text..."
                      bind:value={manualEdits[i].after}
                    />
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- ─── AI corrections mode ─────────────────────── -->
    {#if inputMode === 'ai' && !previewRoundId}
      <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div class="px-4 py-3 bg-purple-50 border-b border-purple-200">
          <span class="text-sm font-medium text-purple-800">AI korekce</span>
          <span class="text-xs text-purple-600 ml-2">Napište instrukci a Claude ji aplikuje na přeložené texty</span>
        </div>
        <div class="p-4 space-y-3">
          <textarea
            class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none focus:border-purple-400 focus:ring-1 focus:ring-purple-200"
            rows="3"
            placeholder="Napište instrukci, např.: 'Všude kde je realizovat změň na uskutečnit' nebo 'Název města má být Vídeň, ne Vienna' nebo 'Zkontroluj správnost datací'"
            bind:value={aiInstruction}
          ></textarea>
          <div class="flex items-center justify-between">
            <p class="text-xs text-gray-400">
              Analyzuje {$currentProject?.elements?.filter(e => e.czech).length || 0} přeložených elementů
            </p>
            <button
              class="px-4 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
              onclick={submitAi}
              disabled={loading || !aiInstruction.trim()}
            >
              {loading ? 'Claude analyzuje...' : 'Spustit AI korekce'}
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- ─── Preview ────────────────────────────────── -->
    {#if previewRoundId && previewEntries.length > 0}
      <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div class="px-4 py-3 bg-amber-50 border-b border-amber-200 flex items-center justify-between">
          <div>
            <span class="text-sm font-medium text-amber-800">
              Preview kola {previewRoundId}
            </span>
            <span class="text-xs text-amber-600 ml-2">({previewFile})</span>
            {#if previewStats}
              <span class="text-xs text-gray-500 ml-4">
                {previewStats.matched} spárováno
                {#if previewStats.unmatched > 0}
                  | {previewStats.unmatched} nespárováno
                {/if}
                {#if previewStats.low_confidence > 0}
                  | {previewStats.low_confidence} s nízkou shodou
                {/if}
              </span>
            {/if}
          </div>
          <div class="flex gap-2">
            <button
              class="px-3 py-1.5 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              onclick={() => { previewRoundId = null; previewEntries = []; }}
            >
              Zrušit
            </button>
            <button
              class="px-4 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              onclick={applyRound}
              disabled={loading}
            >
              {loading ? 'Aplikuji...' : 'Aplikovat korektury'}
            </button>
          </div>
        </div>
        <div class="overflow-x-auto max-h-[50vh] overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 sticky top-0">
              <tr>
                <th class="text-left px-3 py-2 text-gray-600 font-medium">Původní text</th>
                <th class="text-left px-3 py-2 text-gray-600 font-medium">Oprava</th>
                <th class="text-left px-3 py-2 text-gray-600 font-medium w-40">Poznámka</th>
                <th class="text-center px-3 py-2 text-gray-600 font-medium w-20">Shoda</th>
              </tr>
            </thead>
            <tbody>
              {#each previewEntries as entry}
                <tr class="border-t border-gray-100">
                  <td class="px-3 py-2 text-gray-600 max-w-sm">
                    <span class="line-clamp-2">{entry.before || '—'}</span>
                  </td>
                  <td class="px-3 py-2 text-gray-900 max-w-sm">
                    <span class="line-clamp-2">{entry.after}</span>
                  </td>
                  <td class="px-3 py-2 text-xs text-gray-500 max-w-[10rem] truncate">
                    {entry.notes || ''}
                  </td>
                  <td class="px-3 py-2 text-center">
                    <span class="inline-block px-2 py-0.5 rounded text-xs font-medium {confidenceColor(entry.confidence)}">
                      {confidenceLabel(entry.confidence)}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- ─── Historie kol ───────────────────────────── -->
    <div class="bg-white border border-gray-200 rounded-lg">
      <div class="px-4 py-3 border-b border-gray-200">
        <h3 class="text-sm font-medium text-gray-700">Historie korektur</h3>
      </div>
      {#if loadingRounds}
        <div class="p-8 text-center text-sm text-gray-400">Načítám...</div>
      {:else if rounds.length === 0}
        <div class="p-8 text-center text-sm text-gray-400">Zatím žádné korektury.</div>
      {:else}
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="text-left px-4 py-2 text-gray-600 font-medium">Kolo</th>
              <th class="text-left px-4 py-2 text-gray-600 font-medium">Datum</th>
              <th class="text-left px-4 py-2 text-gray-600 font-medium">Zdroj</th>
              <th class="text-center px-4 py-2 text-gray-600 font-medium">Oprav</th>
              <th class="text-center px-4 py-2 text-gray-600 font-medium">Stav</th>
              <th class="text-right px-4 py-2 text-gray-600 font-medium">Akce</th>
            </tr>
          </thead>
          <tbody>
            {#each rounds as round}
              <tr class="border-t border-gray-100 hover:bg-gray-50">
                <td class="px-4 py-2 font-mono text-xs">{round.round_id}</td>
                <td class="px-4 py-2 text-gray-600">
                  {new Date(round.created_at).toLocaleString('cs-CZ')}
                </td>
                <td class="px-4 py-2 text-gray-600">
                  {round.source_file || round.source_type}
                </td>
                <td class="px-4 py-2 text-center">
                  {round.stats?.entry_count ?? round.stats?.applied ?? '—'}
                </td>
                <td class="px-4 py-2 text-center">
                  {#if round.applied}
                    <span class="inline-block px-2 py-0.5 rounded text-xs bg-green-100 text-green-700">Aplikováno</span>
                  {:else}
                    <span class="inline-block px-2 py-0.5 rounded text-xs bg-yellow-100 text-yellow-700">Čeká</span>
                  {/if}
                </td>
                <td class="px-4 py-2 text-right">
                  {#if round.applied && round.output_key}
                    <button
                      class="text-xs text-blue-600 hover:text-blue-800"
                      onclick={() => downloadRound(round.round_id)}
                    >
                      Stáhnout IDML
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>

  </div>
{/if}
