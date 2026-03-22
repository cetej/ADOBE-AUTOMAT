<script>
  import { currentProject } from '../stores/project.js';
  import { notify } from '../stores/notifications.js';
  import { api } from '../lib/api.js';
  import { loadActiveDoc as fetchActiveDoc } from '../lib/illustrator.js';
  import { navigate } from '../stores/router.js';
  import FileUpload from '../components/FileUpload.svelte';

  let extracting = $state(false);
  let progress = $state(0);
  let aiDoc = $state(null);
  let aiDocLoading = $state(false);

  async function loadActiveDoc() {
    aiDocLoading = true;
    aiDoc = await fetchActiveDoc();
    aiDocLoading = false;
  }

  // Auto-load pri zobrazeni MAP projektu
  $effect(() => {
    if ($currentProject?.type === 'map') {
      loadActiveDoc();
    }
  });

  // IDML state
  let uploadingIdml = $state(false);
  let uploadingSourcePdf = $state(false);
  let uploadingTranslation = $state(false);
  let idmlUploaded = $state(false);
  let sourcePdfUploaded = $state(false);
  let sourcePdfStats = $state(null);
  let translationUploaded = $state(false);

  // Sync IDML state from project
  $effect(() => {
    if ($currentProject?.type === 'idml') {
      idmlUploaded = !!$currentProject.idml_path;
      sourcePdfUploaded = !!$currentProject.source_pdf;
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
      navigate('editor');
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

  async function handleSourcePdfUpload(file) {
    if (!$currentProject) return;
    uploadingSourcePdf = true;
    try {
      const result = await api.uploadSourcePdf($currentProject.id, file);
      sourcePdfStats = result.pdf_match_stats || null;
      currentProject.set(result);
      sourcePdfUploaded = true;
      const updated = sourcePdfStats?.updated || 0;
      const matched = sourcePdfStats?.matched || 0;
      notify(`PDF nahrano: ${matched} bloku sparovano, ${updated} textu aktualizovano`, 'success');
    } catch (e) {
      notify('Chyba uploadu PDF: ' + e.message, 'error');
    } finally {
      uploadingSourcePdf = false;
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

  let extracted = $derived($currentProject?.elements?.length > 0);

  async function extractIdml() {
    if (!$currentProject) return;
    extracting = true;
    try {
      const result = await api.extract($currentProject.id);
      currentProject.set(result);
      notify(`Extrahovano ${result.elements?.length || 0} textu z IDML`, 'success');
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
    <div class="bg-white rounded-xl border border-gray-200 p-8">
      <div class="text-center">
        <div class="text-4xl mb-4">&#x1F5FA;</div>
        <h2 class="text-lg font-semibold mb-4">MAP: Extrakce z Illustratoru</h2>
      </div>

      <!-- Illustrator connection status -->
      <div class="mb-6 p-4 rounded-lg border {aiDoc ? 'bg-green-50 border-green-200' : 'bg-orange-50 border-orange-200'}">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="w-3 h-3 rounded-full {aiDoc ? 'bg-green-500' : aiDocLoading ? 'bg-yellow-400 animate-pulse' : 'bg-red-400'}"></span>
            {#if aiDocLoading}
              <span class="text-sm text-gray-600">Pripojuji k Illustratoru...</span>
            {:else if aiDoc}
              <div>
                <span class="text-sm font-medium text-green-800">Pripojeno</span>
                <p class="text-sm text-green-700 font-semibold">{aiDoc.name}</p>
              </div>
            {:else}
              <div>
                <span class="text-sm font-medium text-orange-800">Nepripojeno</span>
                <p class="text-xs text-orange-600">Oteviete Illustrator s dokumentem a spustte proxy.</p>
              </div>
            {/if}
          </div>
          <button
            class="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-50"
            onclick={loadActiveDoc}
            disabled={aiDocLoading}
          >
            {aiDocLoading ? '...' : 'Obnovit'}
          </button>
        </div>
      </div>

      <div class="text-center">
        {#if $currentProject.elements?.length > 0}
          <p class="text-xs text-orange-500 mb-3">Projekt jiz obsahuje {$currentProject.elements.length} textu. Nova extrakce je prepise.</p>
        {/if}
        <button
          class="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          onclick={startExtraction}
          disabled={extracting || !aiDoc}
        >
          {extracting ? 'Extrahuji...' : $currentProject.elements?.length > 0 ? 'Znovu extrahovat' : 'Spustit extrakci'}
        </button>
        {#if !aiDoc && !aiDocLoading}
          <p class="text-xs text-orange-500 mt-2">Nejprve pripojte Illustrator</p>
        {/if}
      </div>
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
        {#if idmlUploaded && !uploadingIdml}
          <div class="flex items-center justify-between">
            <p class="text-sm text-green-600">
              Soubor: {$currentProject.idml_path?.split('/').pop() || 'nahran'}
            </p>
            <button
              class="text-xs text-blue-600 hover:text-blue-800 underline"
              onclick={() => { idmlUploaded = false; }}
            >Zmenit soubor</button>
          </div>
        {:else}
          <FileUpload
            accept=".idml"
            label="Vyberte IDML soubor"
            onupload={handleIdmlUpload}
            bind:uploading={uploadingIdml}
          />
        {/if}
      </div>

      <!-- Step 2: Extract -->
      <div class="bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full {idmlUploaded ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'} flex items-center justify-center font-bold text-sm">2</span>
          <h2 class="text-lg font-semibold {idmlUploaded ? '' : 'text-gray-400'}">Extrahovat texty</h2>
          {#if extracted}
            <span class="ml-auto text-green-600 text-sm font-medium">{$currentProject.elements.length} elementu</span>
          {/if}
        </div>
        <p class="text-sm text-gray-500 mb-4">
          Rozparsuje Story XML soubory a extrahuje textove elementy (bez master pages).
        </p>
        <button
          class="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          onclick={extractIdml}
          disabled={!idmlUploaded || extracting}
        >
          {extracting ? 'Extrahuji...' : extracted ? 'Znovu extrahovat' : 'Spustit extrakci'}
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

      <!-- Step 3: Upload source PDF (optional, needs extracted elements) -->
      <div class="bg-white rounded-xl border border-gray-200 p-6 {extracted ? '' : 'opacity-50'}">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full {extracted ? 'bg-gray-100 text-gray-600' : 'bg-gray-100 text-gray-400'} flex items-center justify-center font-bold text-sm">3</span>
          <h2 class="text-lg font-semibold">Nahrat zdrojove PDF <span class="text-sm font-normal text-gray-400">(volitelne)</span></h2>
          {#if sourcePdfUploaded}
            <span class="ml-auto text-green-600 text-sm font-medium">Nahrano</span>
          {/if}
        </div>
        <p class="text-xs text-gray-500 mb-3">
          RTT/backgrounder PDF — aktualizuje texty z IDML na nejnovejsi verzi + ulozi backgrounder pro kontext prekladu.
        </p>
        {#if !extracted}
          <p class="text-xs text-orange-500">Nejprve extrahujte texty z IDML (krok 2).</p>
        {:else if sourcePdfUploaded && !uploadingSourcePdf}
          <div class="flex items-center justify-between">
            <p class="text-sm text-green-600">
              Soubor: {$currentProject.source_pdf?.split(/[\\/]/).pop() || 'nahran'}
              {#if sourcePdfStats}
                <span class="text-gray-500 ml-2">({sourcePdfStats.matched} sparovano, {sourcePdfStats.updated} aktualizovano)</span>
              {/if}
            </p>
            <button
              class="text-xs text-blue-600 hover:text-blue-800 underline"
              onclick={() => { sourcePdfUploaded = false; sourcePdfStats = null; }}
            >Zmenit soubor</button>
          </div>
        {:else}
          <FileUpload
            accept=".pdf"
            label="Vyberte zdrojove PDF (RTT)"
            onupload={handleSourcePdfUpload}
            bind:uploading={uploadingSourcePdf}
          />
        {/if}
      </div>

      <!-- Step 4: Upload translation (optional, needs extracted elements) -->
      <div class="bg-white rounded-xl border border-gray-200 p-6 {extracted ? '' : 'opacity-50'}">
        <div class="flex items-center gap-3 mb-4">
          <span class="flex-shrink-0 w-8 h-8 rounded-full {extracted ? 'bg-gray-100 text-gray-600' : 'bg-gray-100 text-gray-400'} flex items-center justify-center font-bold text-sm">4</span>
          <h2 class="text-lg font-semibold">Nahrat CZ preklad <span class="text-sm font-normal text-gray-400">(volitelne)</span></h2>
          {#if translationUploaded}
            <span class="ml-auto text-green-600 text-sm font-medium">Nahrano</span>
          {/if}
        </div>
        {#if !extracted}
          <p class="text-xs text-orange-500">Nejprve extrahujte texty z IDML (krok 2).</p>
        {:else if translationUploaded && !uploadingTranslation}
          <div class="flex items-center justify-between">
            <p class="text-sm text-green-600">
              Soubor: {$currentProject.translation_doc?.split('/').pop() || 'nahran'}
            </p>
            <button
              class="text-xs text-blue-600 hover:text-blue-800 underline"
              onclick={() => { translationUploaded = false; }}
            >Zmenit soubor</button>
          </div>
        {:else}
          <FileUpload
            accept=".docx,.doc,.txt,.rtf"
            label="Vyberte soubor s prekladem"
            onupload={handleTranslationUpload}
            bind:uploading={uploadingTranslation}
          />
        {/if}
      </div>

      <!-- Navigate to editor -->
      {#if extracted}
        <div class="text-center">
          <button
            class="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            onclick={() => navigate('editor')}
          >
            Prejit do editoru ({$currentProject.elements.length} elementu)
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
