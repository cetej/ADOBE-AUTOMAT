<script>
  import { api } from '../lib/api.js';
  import { loadActiveDoc as fetchActiveDoc } from '../lib/illustrator.js';
  import { projectList, currentProject } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { navigate } from '../stores/router.js';

  let loading = $state(false);
  let loadingMsg = $state('');
  let dragOver = $state(false);

  // === Drop zone: hodis soubor, vytvori projekt, nahraje, extrahuje ===
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
    if (file) await processFile(file);
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }

  async function processFile(file) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const name = file.name.replace(/\.\w+$/, '');

    if (ext === 'idml') {
      await quickStartIdml(name, file);
    } else if (ext === 'ai') {
      await quickStartMap(name);
    } else {
      notify('Nepodporovany format. Pouzijte .idml nebo .ai soubor.', 'error');
    }
  }

  async function quickStartIdml(name, file) {
    loading = true;
    try {
      loadingMsg = 'Vytvarim projekt...';
      const project = await api.createProject({ name, type: 'idml' });

      loadingMsg = 'Nahravam IDML...';
      const withFile = await api.uploadIdml(project.id, file);

      loadingMsg = 'Extrahuji texty...';
      const extracted = await api.extract(project.id);

      currentProject.set(extracted);
      notify(`${extracted.elements?.length || 0} textu extrahovano z ${file.name}`, 'success');
      navigate('editor');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      loading = false;
      loadingMsg = '';
    }
  }

  async function quickStartMap(name) {
    loading = true;
    try {
      loadingMsg = 'Vytvarim MAP projekt...';
      const project = await api.createProject({ name, type: 'map' });
      currentProject.set(project);
      notify(`MAP projekt "${name}" vytvoren`, 'success');
      navigate('extractor');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      loading = false;
      loadingMsg = '';
    }
  }

  // === MAP z Illustratoru (bez souboru) ===
  let aiDoc = $state(null);
  let aiDocLoading = $state(false);

  async function loadActiveDoc() {
    aiDocLoading = true;
    aiDoc = null;
    aiDoc = await fetchActiveDoc();
    aiDocLoading = false;
  }

  async function quickStartFromIllustrator() {
    if (!aiDoc?.name) return;
    const name = aiDoc.name.replace(/\.ai$/i, '');
    await quickStartMap(name);
  }

  // === Projekty ===
  async function loadProjects() {
    try {
      const data = await api.listProjects();
      projectList.set(data);
    } catch (e) {
      notify('Chyba pri nacitani projektu: ' + e.message, 'error');
    }
  }

  async function openProject(project) {
    try {
      const full = await api.getProject(project.id);
      currentProject.set(full);
      const hasTexts = full.elements && full.elements.length > 0;
      navigate(hasTexts ? 'editor' : 'extractor');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  async function deleteProject(id, name) {
    if (!confirm(`Smazat projekt "${name}"?`)) return;
    try {
      await api.deleteProject(id);
      notify(`Projekt "${name}" smazan`, 'success');
      loadProjects();
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  loadProjects();
  loadActiveDoc();
</script>

<div class="max-w-4xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Projekty</h1>

  <!-- Drop zone -->
  {#if loading}
    <div class="bg-blue-50 border-2 border-blue-300 rounded-xl p-10 mb-6 text-center">
      <div class="animate-spin inline-block w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full mb-3"></div>
      <p class="text-blue-700 font-medium">{loadingMsg}</p>
    </div>
  {:else}
    <div
      class="border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-colors
             {dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'}"
      ondragover={handleDragOver}
      ondragleave={handleDragLeave}
      ondrop={handleDrop}
      role="region"
      aria-label="File upload area"
    >
      <p class="text-lg font-medium text-gray-700 mb-1">Pretahnete soubor sem</p>
      <p class="text-sm text-gray-400 mb-4">.idml (InDesign) nebo .ai (Illustrator mapa)</p>
      <label class="inline-block px-5 py-2.5 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 text-sm font-medium transition-colors">
        Vybrat soubor
        <input
          type="file"
          accept=".idml,.ai"
          onchange={handleFileSelect}
          class="hidden"
        />
      </label>
    </div>

    <!-- MAP z Illustratoru -->
    <div class="bg-white rounded-xl border border-gray-200 p-4 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="w-3 h-3 rounded-full {aiDoc ? 'bg-green-500' : aiDocLoading ? 'bg-yellow-400 animate-pulse' : 'bg-gray-300'}"></span>
          {#if aiDocLoading}
            <span class="text-sm text-gray-500">Hledam Illustrator...</span>
          {:else if aiDoc}
            <span class="text-sm text-gray-700">Illustrator: <strong>{aiDoc.name}</strong></span>
          {:else}
            <span class="text-sm text-gray-400">Illustrator nepripojen</span>
          {/if}
        </div>
        <div class="flex items-center gap-2">
          <button
            class="text-xs text-gray-500 hover:text-gray-700 underline"
            onclick={loadActiveDoc}
            disabled={aiDocLoading}
          >Obnovit</button>
          {#if aiDoc}
            <button
              class="px-4 py-1.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
              onclick={quickStartFromIllustrator}
            >Extrahovat mapu</button>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  <!-- Project list -->
  {#if $projectList.length === 0}
    <div class="text-center py-10 text-gray-400">
      <p class="text-sm">Zatim zadne projekty.</p>
    </div>
  {:else}
    <div class="space-y-2">
      {#each $projectList as project}
        <div class="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
          <button
            class="flex-1 text-left"
            onclick={() => openProject(project)}
          >
            <div class="flex items-center gap-3">
              <span class="text-xl">{project.type === 'map' ? '\u{1F5FA}' : '\u{1F4F0}'}</span>
              <div>
                <div class="font-medium text-gray-900">{project.name}</div>
                <div class="text-xs text-gray-500 mt-0.5">
                  {project.type.toUpperCase()} &middot;
                  {project.elements?.length || 0} textu &middot;
                  {new Date(project.created_at).toLocaleDateString('cs-CZ')}
                </div>
              </div>
            </div>
          </button>
          <button
            class="text-gray-400 hover:text-red-500 transition-colors p-2"
            onclick={() => deleteProject(project.id, project.name)}
            title="Smazat"
          >
            &#x2715;
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>
