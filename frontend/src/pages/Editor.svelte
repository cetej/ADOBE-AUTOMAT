<script>
  import { currentProject } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { api } from '../lib/api.js';
  import CategorySelect from '../components/CategorySelect.svelte';
  import FilterToolbar from '../components/FilterToolbar.svelte';
  import StatsPanel from '../components/StatsPanel.svelte';

  // Interpretace raw error message z backendu na actionable hlasku.
  // Backend obcas vrati str(KeyError) jako jen "'czech'" nebo str(JSONDecodeError) — uzivatel
  // si je interpretuje jako "spatny API klic". Tady mapujeme na konkretni signal.
  function interpretTranslateError(rawError) {
    if (!rawError) return 'Chyba prekladu: neznama';
    const e = String(rawError).trim();
    // KeyError: 'czech' / 'text' / 'translation' — Claude vratil JSON s nestandardnim klicem
    if (/^['"]?(czech|text|translation|cs|en)['"]?$/i.test(e)) {
      return `Claude vratil JSON s nestandardnim klicem (${e}). Backend by to mel zachytit tolerant mappingem — pokud vidis tuto hlasku, pridej dalsi alias do routers/translate.py.`;
    }
    // JSON parsing
    if (/Neplatny JSON|Invalid control|Expecting value|JSONDecodeError|JSON pole/i.test(e)) {
      return `Chyba parsovani odpovedi z Claude API (raw control chars / unescaped quotes). Detail: ${e.slice(0, 120)}`;
    }
    // API auth
    if (/api[_ -]?key|unauthorized|401|authentication|invalid.*key/i.test(e)) {
      return `Chyba autorizace Claude API — overte ANTHROPIC_API_KEY v .env. Detail: ${e.slice(0, 120)}`;
    }
    // Connection / timeout
    if (/timeout|timed out|connection.*refused|connection.*reset/i.test(e)) {
      return `Spojeni s Claude API selhalo (timeout/connection). Detail: ${e.slice(0, 120)}`;
    }
    // Rate limit
    if (/rate.?limit|429|too many requests/i.test(e)) {
      return `Claude API rate limit — pockejte chvili a zkuste znovu. Detail: ${e.slice(0, 120)}`;
    }
    return `Chyba prekladu: ${e}`;
  }

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
  let translateBatch = $state(0);
  let translateTotalBatches = $state(0);
  let translateFromMemory = $state(0);
  let translateHasBackgrounder = $state(false);
  let uploadingTranslation = $state(false);
  let dragOverTranslation = $state(false);

  // Pipeline state
  let pipelineRunning = $state(false);
  let pipelineProgress = $state('');
  let pipelineResult = $state(null);
  let pipelinePhases = $state([3, 4, 5, 6]);  // default: bez fáze 2
  let pipelineCards = $state({});  // {phase: {status, name, duration_s, tokens, error}}
  let pipelineChangeLog = $state([]);  // [{id, layer, before, after}]
  let showChangeLog = $state(false);
  let showTermDialog = $state(false);
  let termNotes = $state('');  // uzivatelske poznamky k terminologii

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
      // Aktualizovat lokalne — NOVY objekt aby Svelte detekoval zmenu
      const proj = $currentProject;
      const elements = proj.elements.map(e =>
        e.id === el.id ? { ...e, ...result } : e
      );
      currentProject.set({ ...proj, elements });
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
      const proj = $currentProject;
      const elements = proj.elements.map(e =>
        e.id === el.id ? { ...e, ...result } : e
      );
      currentProject.set({ ...proj, elements });
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  async function setCategory(el, category) {
    if (!$currentProject) return;
    try {
      const result = await api.updateText($currentProject.id, el.id, { category });
      const proj = $currentProject;
      const elements = proj.elements.map(e =>
        e.id === el.id ? { ...e, ...result } : e
      );
      currentProject.set({ ...proj, elements });
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  async function translateAll(overwrite = false) {
    if (!$currentProject) return;
    translating = true;
    const untranslated = $currentProject.elements.filter(e => !e.czech && e.contents.trim()).length;
    translateProgress = overwrite ? 'Spoustim preklad vsech...' : `Spoustim preklad ${untranslated} textu...`;
    try {
      const startResult = await api.translate($currentProject.id, { overwrite });
      if (startResult.status === 'done') {
        notify(startResult.message || 'Zadne texty k prekladu', 'info');
        translating = false;
        translateProgress = '';
        return;
      }
      translateHasBackgrounder = startResult.has_backgrounder || false;
      await _pollTranslateProgress();
    } catch (e) {
      notify(interpretTranslateError(e.message), 'error');
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
    translateProgress = `Spoustim preklad ${ids.length} textu...`;
    try {
      const startResult = await api.translate($currentProject.id, { ids });
      if (startResult.status === 'done') {
        notify(startResult.message || 'Zadne texty k prekladu', 'info');
        translating = false;
        translateProgress = '';
        return;
      }
      translateHasBackgrounder = startResult.has_backgrounder || false;
      await _pollTranslateProgress();
    } catch (e) {
      notify(interpretTranslateError(e.message), 'error');
      translating = false;
      translateProgress = '';
    }
  }

  async function _pollTranslateProgress() {
    const id = $currentProject?.id;
    if (!id) return;
    while (true) {
      await new Promise(r => setTimeout(r, 1500));
      try {
        const p = await api.translateProgress(id);
        if (p.status === 'running') {
          translateBatch = p.batch || 0;
          translateTotalBatches = p.total_batches || 0;
          translateFromMemory = p.from_memory || 0;
          if (translateTotalBatches > 0) {
            translateProgress = `Batch ${translateBatch}/${translateTotalBatches}`;
          }
        } else if (p.status === 'done') {
          if (p.project) currentProject.set(p.project);
          const parts = [`Prelozeno ${p.translated} textu`];
          if (p.from_memory > 0) parts.push(`${p.from_memory} z TM`);
          if (p.typo_corrected > 0) parts.push(`${p.typo_corrected} typografie`);
          if (translateHasBackgrounder) parts.push('s backgrounderem');
          notify(parts.join(', '), 'success');
          translating = false;
          translateProgress = '';
          return;
        } else if (p.status === 'error') {
          notify(interpretTranslateError(p.error), 'error');
          translating = false;
          translateProgress = '';
          return;
        } else if (p.status === 'idle') {
          translating = false;
          translateProgress = '';
          return;
        }
      } catch (e) {
        notify('Chyba pri polling progresu prekladu: ' + e.message, 'error');
        translating = false;
        translateProgress = '';
        return;
      }
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

  // === Text Pipeline (post-translation phases 2-6) — async + polling ===
  let pollTimer = null;

  async function runPipeline() {
    if (!$currentProject) return;
    const hasTranslated = $currentProject.elements.some(e => e.czech);
    if (!hasTranslated) {
      notify('Nejdrive prelozte texty', 'warning');
      return;
    }
    pipelineRunning = true;
    pipelineResult = null;
    pipelineChangeLog = [];
    showChangeLog = false;
    pipelineCards = {};
    pipelineProgress = 'Pipeline startuje...';

    const opts = { phases: pipelinePhases };
    if (termNotes.trim()) {
      opts.term_notes = termNotes.trim();
    }

    try {
      await api.processText($currentProject.id, opts);
      // Pipeline bezi na pozadi — startni polling
      startPolling();
    } catch (e) {
      // Mozna uz bezi (409) — zkusit polling
      if (e.message?.includes('již běží') || e.message?.includes('409')) {
        startPolling();
      } else {
        notify('Chyba pipeline: ' + e.message, 'error');
        pipelineRunning = false;
        pipelineProgress = '';
      }
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollProgress, 2000);
    pollProgress(); // hned prvni
  }

  async function pollProgress() {
    if (!$currentProject) return;
    try {
      const p = await api.pipelineProgress($currentProject.id);

      if (p.phases) {
        pipelineCards = p.phases;
      }
      if (p.current_phase) {
        const card = p.phases?.[String(p.current_phase)];
        const name = card?.name || `Faze ${p.current_phase}`;
        pipelineProgress = `${name}... (${p.elapsed_s}s)`;
      }

      if (p.status === 'done' || p.status === 'error') {
        clearInterval(pollTimer);
        pollTimer = null;
        pipelineRunning = false;
        pipelineProgress = '';

        if (p.status === 'done' && p.result) {
          pipelineResult = p.result;
          pipelineChangeLog = p.result.change_log || [];
          if (p.project) {
            currentProject.set(p.project);
          }
          const ok = p.result.phases?.filter(ph => ph.success).length || 0;
          const fail = p.result.phases?.filter(ph => !ph.success).length || 0;
          let msg = `Pipeline: ${ok} fazi OK`;
          if (fail > 0) msg += `, ${fail} selhalo`;
          msg += ` | ${p.result.elements_updated || 0} textu upraveno | ${p.result.total_duration_s || 0}s`;
          notify(msg, fail > 0 ? 'warning' : 'success');
        } else if (p.status === 'error') {
          notify('Chyba pipeline: ' + (p.result?.error || 'neznámá'), 'error');
        }
      }
    } catch (e) {
      // Ignoruj chyby pollingu — zkusi znovu za 2s
    }
  }

  // Při vstupu na stránku — zkontroluj jestli pipeline běží
  let checkedPipelineFor = null;
  $effect(() => {
    const id = $currentProject?.id;
    if (id && id !== checkedPipelineFor) {
      checkedPipelineFor = id;
      api.pipelineProgress(id).then(p => {
        if (p.status === 'running') {
          pipelineRunning = true;
          pipelineCards = p.phases || {};
          pipelineProgress = 'Pipeline běží...';
          startPolling();
        }
      }).catch(() => {});
    }
  });

  function togglePhase(phase) {
    if (pipelinePhases.includes(phase)) {
      pipelinePhases = pipelinePhases.filter(p => p !== phase);
    } else {
      pipelinePhases = [...pipelinePhases, phase].sort();
    }
  }

  async function loadChangeLog() {
    if (!$currentProject) return;
    try {
      const res = await api.pipelineChanges($currentProject.id);
      pipelineChangeLog = res.changes || [];
      showChangeLog = true;
    } catch (e) {
      notify('Nelze nacist protokol: ' + e.message, 'error');
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
          <div class="flex items-center gap-3 min-w-[300px]">
            <!-- Progress bar -->
            <div class="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
              <div
                class="bg-violet-600 h-2.5 rounded-full transition-all duration-500"
                style="width: {translateTotalBatches > 0 ? Math.round((translateBatch / translateTotalBatches) * 100) : 0}%"
              ></div>
            </div>
            <div class="flex flex-col items-end gap-0.5 text-xs whitespace-nowrap">
              <span class="text-violet-700 font-medium">
                {#if translateTotalBatches > 0}
                  Batch {translateBatch}/{translateTotalBatches}
                {:else}
                  <span class="animate-pulse">Spoustim...</span>
                {/if}
              </span>
              <div class="flex gap-2 text-gray-500">
                {#if translateFromMemory > 0}
                  <span title="Preklady z Translation Memory">TM: {translateFromMemory}</span>
                {/if}
                {#if translateHasBackgrounder}
                  <span class="text-emerald-600" title="Preklad pouziva backgrounder z PDF">PDF</span>
                {/if}
              </div>
            </div>
          </div>
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

    <!-- Pipeline panel — post-translation processing -->
    {#if $currentProject?.elements?.some(e => e.czech)}
      <div class="bg-indigo-50 border border-indigo-200 rounded-xl p-3 mb-4">
        <!-- Hlavicka + ovladani -->
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <p class="text-sm font-medium text-indigo-800">Text Pipeline</p>
            <div class="flex items-center gap-2 mt-1">
              {#each [[2, 'Uplnost'], [3, 'Terminy'], [4, 'Fakta'], [5, 'Jazyk'], [6, 'Stylistika']] as [num, label]}
                <label class="inline-flex items-center gap-1 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pipelinePhases.includes(num)}
                    onchange={() => togglePhase(num)}
                    disabled={pipelineRunning}
                    class="w-3 h-3 rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span class="text-indigo-700">{num}: {label}</span>
                </label>
              {/each}
            </div>
          </div>
          <div class="flex items-center gap-2">
            {#if !pipelineRunning}
              <button
                onclick={() => showTermDialog = !showTermDialog}
                class="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors"
                title="Poznamky k terminologii"
              >Terminy?</button>
            {/if}
            {#if pipelineRunning}
              <span class="text-xs text-indigo-600 animate-pulse">{pipelineProgress}</span>
            {:else}
              <button
                onclick={runPipeline}
                disabled={pipelinePhases.length === 0}
                class="px-4 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >Spustit pipeline</button>
            {/if}
          </div>
        </div>

        <!-- Dialog pro terminologii -->
        {#if showTermDialog}
          <div class="mt-2 bg-amber-50 border border-amber-200 rounded-lg p-2">
            <p class="text-xs font-medium text-amber-800 mb-1">Poznamky k prekladu terminu</p>
            <p class="text-xs text-amber-600 mb-1">Specifikujte nejasne terminy, preferovane preklady, kontext...</p>
            <textarea
              bind:value={termNotes}
              class="w-full text-xs border border-amber-300 rounded p-2 h-16 resize-y focus:outline-none focus:ring-1 focus:ring-amber-400"
              placeholder='Napr: "Harappan" = Harappska (civilizace), "Indus" = Indus (reka, neprekladat)'
            ></textarea>
          </div>
        {/if}

        <!-- Karty fazi — live progress -->
        {#if Object.keys(pipelineCards).length > 0}
          <div class="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {#each Object.entries(pipelineCards).sort((a,b) => a[0]-b[0]) as [phase, card]}
              <div class="rounded-lg p-2 text-xs border
                {card.status === 'waiting' ? 'bg-gray-50 border-gray-200 text-gray-500' :
                 card.status === 'running' ? 'bg-blue-50 border-blue-300 text-blue-700' :
                 card.status === 'done' && card.success !== false ? 'bg-green-50 border-green-300 text-green-700' :
                 'bg-red-50 border-red-300 text-red-700'}">
                <div class="font-medium flex items-center gap-1">
                  {#if card.status === 'running'}
                    <span class="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
                  {:else if card.status === 'done' && card.success !== false}
                    <span class="text-green-600">&#10003;</span>
                  {:else if card.status === 'failed' || card.success === false}
                    <span class="text-red-600">&#10007;</span>
                  {:else}
                    <span class="text-gray-400">&#9679;</span>
                  {/if}
                  {phase}: {card.name}
                </div>
                {#if card.duration_s}
                  <div class="text-[10px] mt-0.5 opacity-75">{card.duration_s}s{#if card.tokens}, {card.tokens} tok{/if}</div>
                {/if}
                {#if card.error}
                  <div class="text-[10px] mt-0.5 text-red-600 truncate" title={card.error}>{card.error}</div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}

        <!-- Vysledky + protokol oprav -->
        {#if pipelineResult && !pipelineRunning}
          <div class="mt-2 flex items-center gap-2 text-xs text-indigo-700">
            <span>{pipelineResult.elements_updated || 0} textu upraveno</span>
            <span class="text-gray-300">|</span>
            <span>{pipelineResult.total_tokens || 0} tokenu</span>
            <span class="text-gray-300">|</span>
            <span>{pipelineResult.total_duration_s || 0}s</span>
            {#if pipelineChangeLog.length > 0}
              <button
                onclick={() => showChangeLog = !showChangeLog}
                class="ml-auto px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200 transition-colors"
              >{showChangeLog ? 'Skryt' : 'Zobrazit'} protokol ({pipelineChangeLog.length})</button>
            {/if}
          </div>
        {/if}

        <!-- Protokol oprav -->
        {#if showChangeLog && pipelineChangeLog.length > 0}
          <div class="mt-2 bg-white border border-indigo-200 rounded-lg max-h-64 overflow-y-auto">
            <table class="w-full text-xs">
              <thead class="bg-indigo-50 sticky top-0">
                <tr>
                  <th class="px-2 py-1 text-left text-indigo-700 font-medium w-32">Element</th>
                  <th class="px-2 py-1 text-left text-indigo-700 font-medium">Pred</th>
                  <th class="px-2 py-1 text-left text-indigo-700 font-medium">Po</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-indigo-100">
                {#each pipelineChangeLog as ch}
                  <tr class="hover:bg-indigo-50/50">
                    <td class="px-2 py-1 text-gray-500 truncate max-w-[120px]" title={ch.id}>{ch.id}</td>
                    <td class="px-2 py-1 text-red-600/70 font-mono line-through">{ch.before}</td>
                    <td class="px-2 py-1 text-green-700 font-mono font-medium">{ch.after}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}

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
              {#each filtered as el, i (el.id)}
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
                        {#if el.notes && !el.notes.includes('[PDF UPDATE]')}
                          <span class="block text-xs text-gray-400 mt-0.5">{el.notes}</span>
                        {:else if el.notes?.includes('[PDF UPDATE]')}
                          <span class="block text-xs text-amber-500 mt-0.5" title={el.notes}>⚠ PDF update — najet myší</span>
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
