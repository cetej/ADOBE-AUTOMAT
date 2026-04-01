<script>
  import Toast from './components/Toast.svelte';
  import ConnectionBadge from './components/ConnectionBadge.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import Extractor from './pages/Extractor.svelte';
  import Editor from './pages/Editor.svelte';
  import Outputs from './pages/Outputs.svelte';
  import WriteBack from './pages/WriteBack.svelte';
  import Korektury from './pages/Korektury.svelte';
  import LayoutWizard from './pages/LayoutWizard.svelte';
  import PatternEditor from './pages/PatternEditor.svelte';
  import Traces from './pages/Traces.svelte';
  import { currentProject } from './stores/project.js';
  import { page as pageStore, pendingProjectId, queryParams, goHome as navGoHome, navigate } from './stores/router.js';
  import { api } from './lib/api.js';
  import { get } from 'svelte/store';

  // Primo subscribe bez $effect — callback nastavi $state
  let currentPage = $state('dashboard');
  let loadingProject = $state(false);
  let currentQuery = $state({});
  let currentProjectId = $state(null);
  pageStore.subscribe(v => { currentPage = v; });
  queryParams.subscribe(v => { currentQuery = v || {}; });
  pendingProjectId.subscribe(v => { currentProjectId = v; });

  // Po refreshi — načíst projekt z hash (jen lokalizacni projekty, ne layout-wizard/pattern-editor)
  pendingProjectId.subscribe(id => {
    if (id && !$currentProject && get(pageStore) !== 'layout-wizard' && get(pageStore) !== 'pattern-editor') {
      loadingProject = true;
      api.getProject(id).then(p => {
        if (p && p.id) currentProject.set(p);
      }).catch(() => {
        // Projekt nenalezen — zpět na dashboard
        navGoHome();
      }).finally(() => {
        loadingProject = false;
      });
    }
  });

  function goHome() {
    currentProject.set(null);
    navGoHome();
  }
</script>

<div class="min-h-screen bg-gray-50">
  <header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-4">
      <button class="text-lg font-bold text-gray-900 hover:text-blue-600 transition-colors" onclick={goHome}>
        NGM Localizer
      </button>
      {#if $currentProject}
        <span class="text-gray-400">/</span>
        <span class="text-sm text-gray-600">{$currentProject.name}</span>
        <span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-500 uppercase">
          {$currentProject.type}
        </span>
      {/if}
    </div>
    <div class="flex items-center gap-3">
      <button
        class="text-xs px-3 py-1.5 rounded-full transition-colors
               {currentPage === 'traces' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500 hover:text-gray-700'}"
        onclick={() => navigate('traces')}
      >
        Traces
      </button>
      <ConnectionBadge />
    </div>
  </header>

  {#if $currentProject}
    <nav class="bg-white border-b border-gray-200 px-6">
      <div class="flex gap-1">
        {#each [
          { id: 'extractor', label: 'Extrakce' },
          { id: 'editor', label: 'Editor' },
          { id: 'outputs', label: 'V\u00fdstupy' },
          { id: 'writeback', label: 'Z\u00e1pis' },
          { id: 'korektury', label: 'Korektury' },
        ] as tab}
          <button
            class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                   {currentPage === tab.id
                     ? 'border-blue-500 text-blue-600'
                     : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
            onclick={() => navigate(tab.id)}
          >
            {tab.label}
          </button>
        {/each}
      </div>
    </nav>
  {/if}

  <main class="p-6">
    {#if loadingProject}
      <div class="text-center py-16 text-gray-500">
        <div class="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p class="text-sm">Nacitam projekt...</p>
      </div>
    {:else if currentPage === 'pattern-editor'}
      <PatternEditor />
    {:else if currentPage === 'layout-wizard'}
      {#key currentProjectId}
        <LayoutWizard
          projectId={currentProjectId}
          initialStyle={currentQuery.style || 'ng_feature'}
        />
      {/key}
    {:else if currentPage === 'traces'}
      <Traces />
    {:else if currentPage === 'dashboard'}
      <Dashboard />
    {:else if currentPage === 'extractor'}
      <Extractor />
    {:else if currentPage === 'editor'}
      <Editor />
    {:else if currentPage === 'outputs'}
      <Outputs />
    {:else if currentPage === 'writeback'}
      <WriteBack />
    {:else if currentPage === 'korektury'}
      <Korektury />
    {:else}
      <Dashboard />
    {/if}
  </main>
</div>

<Toast />
