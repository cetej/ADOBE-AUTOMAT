<script>
  import { currentProject, currentPage } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { api } from '../lib/api.js';
  import FileUpload from '../components/FileUpload.svelte';

  let { navigate } = $props();

  function go(target) {
    window.location.hash = target;
    currentPage.set(target);
  }

  let extracting = $state(false);
  let progress = $state(0);

  // IDML state
  let uploadingIdml = $state(false);
  let uploadingTranslation = $state(false);
  let idmlUploaded = $state(false);
  let translationUploaded = $state(false);

  // Sync IDML state from project
  $effect(() => {
    if ($currentProject?.type === 'idml') {
      idmlUploaded = !!$currentProject.idml_path;
      translationUploaded = !!$currentProject.translation_doc;
    }
  });

  // === MAP ===
  async function startExtraction() {
    if (!$currentProject) return;
    extracting = true;
    progress = 0;
    try {
      const result = await api.extract($currentProject.id);
      currentProject.set(result);
      notify(`Extrahovano ${result.elements?.length || 0} textu`, 'success');
      go('editor');
    } catch (e) {
      notify('Chyba extrakce: ' + e.message, 'error');
    } finally {
      extracting = false;
    }
  }

  // === IDML ===
  async function handleIdmlUpload(file) {
    if (!$currentProject) return;
    uploadingIdml = true;
    try {
      const result = await api.uploadIdml($currentProject.id, file);
      currentProject.set(result);
      idmlUploaded = true;
      notify('IDML soubor nahran', 'success');
    } catch (e) {
      notify('Chyba uploadu: ' + e.message, 'error');
    } finally {
      uploadingIdml = false;
    }
  }

  async function handleTranslationUpload(file) {
    if (!$currentProject) return;
    uploadingTranslation = true;
    try {
      const result = await api.uploadTranslation($currentProject.id, file);
      currentProject.set(result);
      translationUploaded = true;
      notify('Preklad nahran', 'success');
    } catch (e) {
      notify('Chyba uploadu: ' + e.message, 'error');
    } finally {
      uploadingTranslation = false;
    }
  }

  async function extractIdml() {
    if (!$currentProject) return;
    extracting = true;
    try {
      const result = await api.extract($currentProject.id);
      currentProject.set(result);
      notify(`Extrahovano ${result.elements?.length || 0} textu z IDML`, 'success');
      go('editor');
    } catch (e) {
      notify('Chyba extrakce IDML: ' + e.message, 'error');
    } finally {
      extracting = false;
    }
  }
</script>

<div class="max-w-2xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Extrakce textu</h1>

  {#if !$currentProject}
    <p class="text-gray-500">Zadny projekt neni otevren.</p>

  {:else if $currentProject.type === 'map'}
    <!-- MAP: Illustrator extraction -->
    <div class="bg-white rounded-xl border border-gray-200 p-8 text-center">
      <div class="text-4xl mb-4">&#x1F5FA;</div>
      <h2 class="text-lg font-semibold mb-2">MAP: Extrakce z Illustratoru</h2>
      <p class="text-sm text-gray-500 mb-6">
        Ujistete se, ze je Illustrator otevreny s pozadovanym dokumentem a CEP plugin je pripojeny.
      </p>
      <button
        class="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        onclick={startExtraction}
        disabled={extracting}
      >
        {extracting ? 'Extrahuji...' : 'Spustit extrakci'}
      </button>
      {#if extracting}
        <div class="mt-4">
          <div class="w-full bg-gray-200 rounded-full h-2">
            <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: {progress}%"></div>
          </div>
        </div>
      {/if}
    </div>

  {:else}
    <!-- IDML: Upload + Extract flow -->
    <div class="space-y-6">
      <!-- Step 1: Upload IDML -->
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-sm">1</span>
          <h2 class="text-lg font-semibold">Nahrat IDML soubor</h2>
          {#if idmlUploaded}
            <span class="ml-auto text-green-600 text-sm font-medium">Nahrano</span>
          {/if}
        </div>
        {#if idmlUploaded}
          <p class="text-sm text-green-600">
            Soubor: {$currentProject.idml_path?.split('/').pop() || 'nahran'}
          </p>
        {:else}
          <FileUpload
            accept=".idml"
            label="Vyberte IDML soubor"
            onupload={handleIdmlUpload}
            bind:uploading={uploadingIdml}
          />
        {/if}
      </div>

      <!-- Step 2: Upload translation (optional) -->
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center font-bold text-sm">2</span>
          <h2 class="text-lg font-semibold">Nahrat CZ preklad <span class="text-sm font-normal text-gray-400">(volitelne)</span></h2>
          {#if translationUploaded}
            <span class="ml-auto text-green-600 text-sm font-medium">Nahrano</span>
          {/if}
        </div>
        {#if translationUploaded}
          <p class="text-sm text-green-600">
            Soubor: {$currentProject.translation_doc?.split('/').pop() || 'nahran'}
          </p>
        {:else}
          <FileUpload
            accept=".docx,.doc,.txt,.rtf"
            label="Vyberte soubor s prekladem"
            onupload={handleTranslationUpload}
            bind:uploading={uploadingTranslation}
          />
        {/if}
      </div>

      <!-- Step 3: Extract -->
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full {idmlUploaded ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'} flex items-center justify-center font-bold text-sm">3</span>
          <h2 class="text-lg font-semibold {idmlUploaded ? '' : 'text-gray-400'}">Extrahovat texty</h2>
        </div>
        <p class="text-sm text-gray-500 mb-4">
          Rozparsuje Story XML soubory a extrahuje vsechny textove elementy.
        </p>
        <button
          class="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          onclick={extractIdml}
          disabled={!idmlUploaded || extracting}
        >
          {extracting ? 'Extrahuji...' : 'Spustit extrakci'}
        </button>
        {#if extracting}
          <div class="mt-4">
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div class="bg-blue-600 h-2 rounded-full transition-all animate-pulse" style="width: 60%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-1">Parsovani Story XML...</p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
