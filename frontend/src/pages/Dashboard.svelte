<script>
  import { api } from '../lib/api.js';
  import { loadActiveDoc as fetchActiveDoc } from '../lib/illustrator.js';
  import { projectList, currentProject } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { navigate } from '../stores/router.js';

  let loading = $state(false);
  let loadingMsg = $state('');
  let dragOver = $state(false);

  // === Lokalizace — Drop zone ===
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

  // === Illustrator ===
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

  // === Projekty — lokalizace ===
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

  // === Layout projekty ===
  let layoutProjects = $state([]);
  let layoutTemplates = $state([]);
  let activeTab = $state('localization'); // 'localization' | 'layout'

  async function loadLayoutProjects() {
    try {
      const data = await api.layoutListProjects();
      layoutProjects = data.projects || [];
    } catch (e) {
      // Layout API mozna neni dostupne — tichy fail
    }
  }

  async function loadLayoutTemplates() {
    try {
      const data = await api.layoutTemplates();
      layoutTemplates = data.profiles || [];
    } catch (e) {
      // Tichy fail
    }
  }

  function openLayoutProject(project) {
    navigate(`layout-wizard/${project.id}`);
  }

  async function deleteLayoutProject(id, name) {
    if (!confirm(`Smazat layout "${name}"?`)) return;
    try {
      await api.layoutDeleteProject(id);
      notify(`Layout "${name}" smazan`, 'success');
      loadLayoutProjects();
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  function startLayoutWizard(profileId = 'ng_feature') {
    navigate(`layout-wizard?style=${profileId}`);
  }

  loadProjects();
  loadActiveDoc();
  loadLayoutProjects();
  loadLayoutTemplates();
</script>

<div class="max-w-6xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-900 mb-6">NGM Localizer</h1>

  <!-- Dva smery -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

    <!-- LEVY SLOUPEC: Lokalizace -->
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-2xl">&#x1F4E5;</span>
        <div>
          <h2 class="text-lg font-bold text-gray-900">Lokalizace</h2>
          <p class="text-sm text-gray-500">Preklad a lokalizace IDML / MAP</p>
        </div>
      </div>

      {#if loading}
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <div class="animate-spin inline-block w-7 h-7 border-2 border-blue-600 border-t-transparent rounded-full mb-2"></div>
          <p class="text-blue-700 font-medium text-sm">{loadingMsg}</p>
        </div>
      {:else}
        <!-- Drop zone -->
        <div
          class="border-2 border-dashed rounded-lg p-6 text-center transition-colors mb-4
                 {dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}"
          ondragover={handleDragOver}
          ondragleave={handleDragLeave}
          ondrop={handleDrop}
          role="region"
          aria-label="File upload area"
        >
          <p class="text-sm font-medium text-gray-700 mb-1">Pretahnete soubor</p>
          <p class="text-xs text-gray-400 mb-3">.idml nebo .ai</p>
          <label class="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 text-xs font-medium transition-colors">
            Vybrat soubor
            <input
              type="file"
              accept=".idml,.ai"
              onchange={handleFileSelect}
              class="hidden"
            />
          </label>
        </div>

        <!-- Illustrator -->
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full {aiDoc ? 'bg-green-500' : aiDocLoading ? 'bg-yellow-400 animate-pulse' : 'bg-gray-300'}"></span>
            {#if aiDocLoading}
              <span class="text-xs text-gray-500">Hledam Illustrator...</span>
            {:else if aiDoc}
              <span class="text-xs text-gray-700">AI: <strong>{aiDoc.name}</strong></span>
            {:else}
              <span class="text-xs text-gray-400">Illustrator nepripojen</span>
            {/if}
          </div>
          <div class="flex items-center gap-2">
            <button class="text-xs text-gray-500 hover:text-gray-700 underline" onclick={loadActiveDoc} disabled={aiDocLoading}>Obnovit</button>
            {#if aiDoc}
              <button class="px-3 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700 transition-colors" onclick={quickStartFromIllustrator}>Extrahovat</button>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <!-- PRAVY SLOUPEC: Layout Generator -->
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-2xl">&#x1F4D0;</span>
        <div>
          <h2 class="text-lg font-bold text-gray-900">Layout Generator</h2>
          <p class="text-sm text-gray-500">Vytvor novy layout z fotek a textu</p>
        </div>
      </div>

      <p class="text-sm text-gray-600 mb-4">Zvol styl a spust wizard:</p>

      <div class="space-y-2 mb-4">
        {#if layoutTemplates.length > 0}
          {#each layoutTemplates as tpl}
            <button
              class="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-colors group"
              onclick={() => startLayoutWizard(tpl.id)}
            >
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-sm font-medium text-gray-900 group-hover:text-blue-700">{tpl.name}</div>
                  <div class="text-xs text-gray-500">{tpl.page_width}x{tpl.page_height}pt, {tpl.columns} sloupcu</div>
                </div>
                <span class="text-gray-400 group-hover:text-blue-500 text-lg">&rarr;</span>
              </div>
            </button>
          {/each}
        {:else}
          <!-- Fallback kdyz API neni dostupne -->
          <button
            class="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-colors group"
            onclick={() => startLayoutWizard('ng_feature')}
          >
            <div class="flex items-center justify-between">
              <div>
                <div class="text-sm font-medium text-gray-900 group-hover:text-blue-700">NG Reportaz</div>
                <div class="text-xs text-gray-500">Standardni feature layout</div>
              </div>
              <span class="text-gray-400 group-hover:text-blue-500 text-lg">&rarr;</span>
            </div>
          </button>
          <button
            class="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-colors group"
            onclick={() => startLayoutWizard('ng_medium_feature')}
          >
            <div class="flex items-center justify-between">
              <div>
                <div class="text-sm font-medium text-gray-900 group-hover:text-blue-700">NG Kratka zprava</div>
                <div class="text-xs text-gray-500">Medium Feature layout</div>
              </div>
              <span class="text-gray-400 group-hover:text-blue-500 text-lg">&rarr;</span>
            </div>
          </button>
        {/if}
      </div>

      <button
        class="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        onclick={() => startLayoutWizard('ng_feature')}
      >
        Novy layout
      </button>
    </div>
  </div>

  <!-- Projekty — Tabs -->
  <div class="flex gap-1 mb-4 border-b border-gray-200">
    <button
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
             {activeTab === 'localization' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}"
      onclick={() => { activeTab = 'localization'; }}
    >
      Lokalizace ({$projectList.length})
    </button>
    <button
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
             {activeTab === 'layout' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}"
      onclick={() => { activeTab = 'layout'; }}
    >
      Layouty ({layoutProjects.length})
    </button>
  </div>

  <!-- Seznam projektu -->
  {#if activeTab === 'localization'}
    {#if $projectList.length === 0}
      <div class="text-center py-8 text-gray-400">
        <p class="text-sm">Zatim zadne lokalizacni projekty.</p>
      </div>
    {:else}
      <div class="space-y-2">
        {#each $projectList as project}
          <div class="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
            <button class="flex-1 text-left" onclick={() => openProject(project)}>
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
            >&#x2715;</button>
          </div>
        {/each}
      </div>
    {/if}

  {:else}
    {#if layoutProjects.length === 0}
      <div class="text-center py-8 text-gray-400">
        <p class="text-sm">Zatim zadne layout projekty.</p>
      </div>
    {:else}
      <div class="space-y-2">
        {#each layoutProjects as project}
          <div class="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
            <button class="flex-1 text-left" onclick={() => openLayoutProject(project)}>
              <div class="flex items-center gap-3">
                <span class="text-xl">&#x1F4D0;</span>
                <div>
                  <div class="font-medium text-gray-900">{project.name}</div>
                  <div class="text-xs text-gray-500 mt-0.5">
                    {project.phase} &middot;
                    {project.images?.length || 0} fotek &middot;
                    {new Date(project.created_at).toLocaleDateString('cs-CZ')}
                  </div>
                </div>
              </div>
            </button>
            <button
              class="text-gray-400 hover:text-red-500 transition-colors p-2"
              onclick={() => deleteLayoutProject(project.id, project.name)}
              title="Smazat"
            >&#x2715;</button>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
