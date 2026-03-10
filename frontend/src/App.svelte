<script>
  import Toast from './components/Toast.svelte';
  import ConnectionBadge from './components/ConnectionBadge.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import Extractor from './pages/Extractor.svelte';
  import Editor from './pages/Editor.svelte';
  import Outputs from './pages/Outputs.svelte';
  import WriteBack from './pages/WriteBack.svelte';
  import { currentProject } from './stores/project.js';
  import { page as pageStore, goHome as navGoHome, navigate } from './stores/router.js';

  // Primo subscribe bez $effect — callback nastavi $state
  let currentPage = $state('dashboard');
  pageStore.subscribe(v => { currentPage = v; });

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
      <ConnectionBadge />
    </div>
  </header>

  {#if $currentProject}
    <nav class="bg-white border-b border-gray-200 px-6">
      <div class="flex gap-1">
        {#each [
          { id: 'extractor', label: 'Extrakce' },
          { id: 'editor', label: 'Editor' },
          { id: 'outputs', label: 'Vystupy' },
          { id: 'writeback', label: 'Zapis' },
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
    {#if currentPage === 'dashboard'}
      <Dashboard />
    {:else if currentPage === 'extractor'}
      <Extractor />
    {:else if currentPage === 'editor'}
      <Editor />
    {:else if currentPage === 'outputs'}
      <Outputs />
    {:else if currentPage === 'writeback'}
      <WriteBack />
    {:else}
      <Dashboard />
    {/if}
  </main>
</div>

<Toast />
