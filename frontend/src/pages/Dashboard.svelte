<script>
  import { api } from '../lib/api.js';
  import { projectList, currentProject, currentPage } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import ProjectTypeSelect from '../components/ProjectTypeSelect.svelte';

  let { navigate } = $props();

  function go(target) {
    window.location.hash = target;
    currentPage.set(target);
  }

  let showCreate = $state(false);
  let newName = $state('');
  let newType = $state('map');
  let loading = $state(false);

  async function loadProjects() {
    try {
      const data = await api.listProjects();
      projectList.set(data);
    } catch (e) {
      notify('Chyba pri nacitani projektu: ' + e.message, 'error');
    }
  }

  async function createProject() {
    if (!newName.trim()) return;
    loading = true;
    try {
      const project = await api.createProject({ name: newName.trim(), type: newType });
      notify(`Projekt "${project.name}" vytvoren`, 'success');
      showCreate = false;
      newName = '';
      currentProject.set(project);
      go('extractor');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      loading = false;
    }
  }

  async function openProject(project) {
    try {
      const full = await api.getProject(project.id);
      currentProject.set(full);
      const hasTexts = full.elements && full.elements.length > 0;
      go(hasTexts ? 'editor' : 'extractor');
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

  // Nacist projekty pri zobrazeni
  loadProjects();
</script>

<div class="max-w-4xl mx-auto">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Projekty</h1>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
      onclick={() => (showCreate = true)}
    >
      + Novy projekt
    </button>
  </div>

  <!-- Create dialog -->
  {#if showCreate}
    <div class="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
      <h2 class="text-lg font-semibold mb-4">Novy projekt</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Nazev projektu</label>
          <input
            type="text"
            bind:value={newName}
            placeholder="napr. Byzantine Empire AD 717"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            onkeydown={(e) => e.key === 'Enter' && createProject()}
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Typ projektu</label>
          <ProjectTypeSelect bind:value={newType} />
        </div>
        <div class="flex gap-2 justify-end">
          <button
            class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            onclick={() => (showCreate = false)}
          >
            Zrusit
          </button>
          <button
            class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            onclick={createProject}
            disabled={loading || !newName.trim()}
          >
            {loading ? 'Vytvari se...' : 'Vytvorit'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Project list -->
  {#if $projectList.length === 0}
    <div class="text-center py-16 text-gray-500">
      <div class="text-4xl mb-3">&#x1F4C1;</div>
      <p class="text-lg">Zadne projekty</p>
      <p class="text-sm mt-1">Vytvorte novy projekt tlacitkem vyse.</p>
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
