<script>
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';
  import { navigate } from '../stores/router.js';

  // Props — projectId z URL hash
  let { projectId = null, initialStyle = 'ng_feature' } = $props();

  // Wizard state
  let step = $state(1); // 1-6
  let projectMeta = $state(null);
  let createdProjectId = $state(projectId);

  // Step 1: Styl
  let templates = $state([]);
  let selectedStyle = $state(initialStyle);

  // Step 2: Fotky
  let imageFiles = $state([]);
  let imagePreviews = $state([]);
  let uploadedImages = $state([]);
  let uploading = $state(false);
  let heroIndex = $state(0);

  // Step 3: Text
  let articleText = $state('');
  let textInfo = $state(null);
  let textUploading = $state(false);

  // Step 4: Nastaveni
  let numPages = $state('auto');
  let useAi = $state(false);

  // Step 5: Plan preview
  let planResult = $state(null);
  let planning = $state(false);
  let planMessage = $state('');

  // Step 6: Generate
  let generating = $state(false);
  let generateMessage = $state('');
  let generateResult = $state(null);

  const STEPS = [
    { num: 1, label: 'Styl' },
    { num: 2, label: 'Fotky' },
    { num: 3, label: 'Text' },
    { num: 4, label: 'Nastaveni' },
    { num: 5, label: 'Plan' },
    { num: 6, label: 'Generovani' },
  ];

  // === Init ===
  async function init() {
    try {
      const data = await api.layoutTemplates();
      templates = data.profiles || [];
    } catch (e) {
      // Fallback
    }

    // Pokud mame projectId — nacist stav
    if (projectId) {
      try {
        const data = await api.layoutGetProject(projectId);
        projectMeta = data.project;
        createdProjectId = projectMeta.id;
        selectedStyle = projectMeta.style_profile || 'ng_feature';
        uploadedImages = projectMeta.images || [];
        if (projectMeta.article) {
          textInfo = {
            headline: projectMeta.article.headline || '',
            body_paragraphs: projectMeta.article.body_paragraphs?.length || 0,
            total_chars: projectMeta.article.total_chars || 0,
          };
        }
        if (projectMeta.plan) {
          planResult = projectMeta.plan;
        }
        // Urcit krok podle faze
        if (projectMeta.generated_idml) step = 6;
        else if (projectMeta.plan) step = 5;
        else if (projectMeta.article) step = 4;
        else if (uploadedImages.length) step = 3;
        else step = 1;
      } catch (e) {
        notify('Chyba: ' + e.message, 'error');
      }
    }
  }
  init();

  // === Step 1: Volba stylu + vytvoreni projektu ===
  async function createProject() {
    if (createdProjectId) {
      step = 2;
      return;
    }
    try {
      const name = `Layout ${new Date().toLocaleDateString('cs-CZ')} ${selectedStyle}`;
      const data = await api.layoutCreateProject({ name, style_profile: selectedStyle });
      createdProjectId = data.project_id;
      projectMeta = data.meta;
      step = 2;
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  // === Step 2: Upload fotek ===
  function handleImageDragOver(e) { e.preventDefault(); }

  function handleImageDrop(e) {
    e.preventDefault();
    addFiles(Array.from(e.dataTransfer?.files || []));
  }

  function handleImageSelect(e) {
    addFiles(Array.from(e.target.files || []));
    e.target.value = '';
  }

  function addFiles(files) {
    const imgs = files.filter(f => f.type.startsWith('image/'));
    for (const f of imgs) {
      const url = URL.createObjectURL(f);
      imageFiles = [...imageFiles, f];
      imagePreviews = [...imagePreviews, { name: f.name, url, size: f.size }];
    }
  }

  function removeImage(idx) {
    URL.revokeObjectURL(imagePreviews[idx]?.url);
    imageFiles = imageFiles.filter((_, i) => i !== idx);
    imagePreviews = imagePreviews.filter((_, i) => i !== idx);
    if (heroIndex >= imagePreviews.length) heroIndex = 0;
  }

  function moveImage(from, to) {
    if (to < 0 || to >= imageFiles.length) return;
    const f = [...imageFiles];
    const p = [...imagePreviews];
    [f[from], f[to]] = [f[to], f[from]];
    [p[from], p[to]] = [p[to], p[from]];
    imageFiles = f;
    imagePreviews = p;
    if (heroIndex === from) heroIndex = to;
    else if (heroIndex === to) heroIndex = from;
  }

  async function uploadImages() {
    if (!createdProjectId || imageFiles.length === 0) return;
    uploading = true;
    try {
      const result = await api.layoutUploadImages(createdProjectId, imageFiles);
      uploadedImages = result.images || [];
      notify(`${result.uploaded} fotek nahrano`, 'success');
      step = 3;
    } catch (e) {
      notify('Chyba uploadu: ' + e.message, 'error');
    } finally {
      uploading = false;
    }
  }

  // === Step 3: Text ===
  function handleTextFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { articleText = reader.result; };
    reader.readAsText(file);
  }

  async function uploadText() {
    if (!createdProjectId || !articleText.trim()) return;
    textUploading = true;
    try {
      const result = await api.layoutUploadText(createdProjectId, articleText);
      textInfo = result;
      notify('Text nahran a rozparsovan', 'success');
      step = 4;
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      textUploading = false;
    }
  }

  // === Step 4: Nastaveni → Step 5: Plan ===
  async function runPlanning() {
    if (!createdProjectId) return;
    planning = true;
    planMessage = 'Spoustim planovani...';
    planResult = null;

    try {
      await api.layoutPlan(createdProjectId, {
        num_pages: numPages,
        use_ai: useAi,
        style_profile: selectedStyle,
      });

      // Polling
      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1000));
        const prog = await api.layoutPlanProgress(createdProjectId);
        planMessage = prog.message || '';
        if (prog.status === 'done') {
          planResult = prog.result?.plan || prog.result;
          done = true;
          step = 5;
        } else if (prog.status === 'error') {
          notify('Chyba planovani: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      planning = false;
    }
  }

  // === Step 6: Generate ===
  async function runGenerate() {
    if (!createdProjectId) return;
    generating = true;
    generateMessage = 'Generuji IDML...';
    generateResult = null;

    try {
      await api.layoutGenerate(createdProjectId);

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1000));
        const prog = await api.layoutGenerateProgress(createdProjectId);
        generateMessage = prog.message || '';
        if (prog.status === 'done') {
          generateResult = prog.result;
          done = true;
        } else if (prog.status === 'error') {
          notify('Chyba generovani: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      generating = false;
    }
  }

  function downloadIdml() {
    if (!createdProjectId) return;
    window.open(api.layoutDownloadUrl(createdProjectId), '_blank');
  }
</script>

<div class="max-w-4xl mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center gap-3">
      <button class="text-gray-500 hover:text-gray-700 text-sm" onclick={() => navigate('dashboard')}>
        &larr; Zpet
      </button>
      <h1 class="text-xl font-bold text-gray-900">Layout Wizard</h1>
    </div>
    {#if createdProjectId}
      <span class="text-xs text-gray-400">ID: {createdProjectId}</span>
    {/if}
  </div>

  <!-- Step indicator -->
  <div class="flex items-center gap-1 mb-8">
    {#each STEPS as s}
      <div class="flex items-center gap-1 flex-1">
        <div class="flex items-center gap-2 flex-1">
          <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                      {step === s.num ? 'bg-indigo-600 text-white' :
                       step > s.num ? 'bg-green-500 text-white' :
                       'bg-gray-200 text-gray-500'}">
            {step > s.num ? '\u2713' : s.num}
          </div>
          <span class="text-xs {step === s.num ? 'text-indigo-600 font-medium' : 'text-gray-400'} hidden sm:inline">
            {s.label}
          </span>
        </div>
        {#if s.num < 6}
          <div class="flex-1 h-0.5 {step > s.num ? 'bg-green-400' : 'bg-gray-200'}"></div>
        {/if}
      </div>
    {/each}
  </div>

  <!-- STEP 1: Styl -->
  {#if step === 1}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Zvol styl layoutu</h2>

      <div class="space-y-3 mb-6">
        {#if templates.length > 0}
          {#each templates as tpl}
            <button
              class="w-full text-left p-4 rounded-lg border-2 transition-colors
                     {selectedStyle === tpl.id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}"
              onclick={() => { selectedStyle = tpl.id; }}
            >
              <div class="font-medium text-gray-900">{tpl.name}</div>
              <div class="text-xs text-gray-500 mt-1">{tpl.page_width} x {tpl.page_height} pt, {tpl.columns} sloupcu</div>
            </button>
          {/each}
        {:else}
          <button
            class="w-full text-left p-4 rounded-lg border-2 transition-colors
                   {selectedStyle === 'ng_feature' ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}"
            onclick={() => { selectedStyle = 'ng_feature'; }}
          >
            <div class="font-medium text-gray-900">NG Reportaz</div>
            <div class="text-xs text-gray-500 mt-1">495 x 720 pt, 12 sloupcu</div>
          </button>
          <button
            class="w-full text-left p-4 rounded-lg border-2 transition-colors
                   {selectedStyle === 'ng_medium_feature' ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}"
            onclick={() => { selectedStyle = 'ng_medium_feature'; }}
          >
            <div class="font-medium text-gray-900">NG Kratka zprava</div>
            <div class="text-xs text-gray-500 mt-1">495 x 720 pt, 12 sloupcu</div>
          </button>
        {/if}
      </div>

      <button
        class="w-full py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
        onclick={createProject}
      >
        Pokracovat &rarr;
      </button>
    </div>

  <!-- STEP 2: Fotky -->
  {:else if step === 2}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Nahraj fotky</h2>

      <!-- Drop area -->
      <div
        class="border-2 border-dashed rounded-lg p-6 text-center mb-4 transition-colors border-gray-300 hover:border-indigo-400"
        ondragover={handleImageDragOver}
        ondrop={handleImageDrop}
        role="region"
        aria-label="Image upload area"
      >
        <p class="text-sm text-gray-600 mb-2">Pretahnete fotky sem nebo</p>
        <label class="inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer hover:bg-indigo-700 text-xs font-medium transition-colors">
          Vybrat soubory
          <input type="file" accept="image/*" multiple onchange={handleImageSelect} class="hidden" />
        </label>
      </div>

      <!-- Preview grid -->
      {#if imagePreviews.length > 0}
        <div class="grid grid-cols-3 sm:grid-cols-4 gap-3 mb-4">
          {#each imagePreviews as img, idx}
            <div class="relative group rounded-lg overflow-hidden border-2 transition-colors
                        {idx === heroIndex ? 'border-yellow-400 ring-2 ring-yellow-200' : 'border-gray-200'}">
              <img src={img.url} alt={img.name} class="w-full h-24 object-cover" />
              <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
                <button class="w-6 h-6 bg-white/80 rounded text-xs" onclick={() => moveImage(idx, idx - 1)} title="Doleva">&larr;</button>
                <button class="w-6 h-6 bg-white/80 rounded text-xs" onclick={() => moveImage(idx, idx + 1)} title="Doprava">&rarr;</button>
                <button class="w-6 h-6 bg-red-500/80 text-white rounded text-xs" onclick={() => removeImage(idx)} title="Smazat">&times;</button>
              </div>
              {#if idx === heroIndex}
                <span class="absolute top-1 left-1 bg-yellow-400 text-yellow-900 text-[10px] font-bold px-1.5 py-0.5 rounded">HERO</span>
              {:else}
                <button
                  class="absolute top-1 left-1 bg-white/70 text-gray-600 text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  onclick={() => { heroIndex = idx; }}
                >Hero</button>
              {/if}
              <div class="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[10px] px-1 py-0.5 truncate">
                {img.name}
              </div>
            </div>
          {/each}
        </div>
        <p class="text-xs text-gray-500 mb-4">{imagePreviews.length} fotek, hero: {imagePreviews[heroIndex]?.name}</p>
      {/if}

      <div class="flex gap-3">
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 1; }}>
          &larr; Zpet
        </button>
        <button
          class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={imageFiles.length === 0 || uploading}
          onclick={uploadImages}
        >
          {#if uploading}
            <span class="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
            Nahravam...
          {:else}
            Nahrat {imageFiles.length} fotek &rarr;
          {/if}
        </button>
      </div>
    </div>

  <!-- STEP 3: Text -->
  {:else if step === 3}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-2">Vloz text clanku</h2>
      <p class="text-xs text-gray-500 mb-4">
        Strukturovany format: <code># HEADLINE:</code>, <code># DECK:</code>, <code># BYLINE:</code>, <code># BODY:</code>, <code># CAPTION:</code> —
        nebo prosty text (auto-detekce).
      </p>

      <div class="mb-3">
        <label class="inline-block px-3 py-1.5 bg-gray-100 text-gray-700 rounded cursor-pointer hover:bg-gray-200 text-xs font-medium transition-colors">
          Nahrat .txt soubor
          <input type="file" accept=".txt,.md,.docx" onchange={handleTextFileSelect} class="hidden" />
        </label>
      </div>

      <textarea
        class="w-full h-64 p-3 border border-gray-300 rounded-lg text-sm font-mono resize-y focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400"
        placeholder="Vloz text clanku zde...

# HEADLINE: Nazev clanku
# DECK: Podnazev
# BYLINE: Autor
# BODY:
Text clanku..."
        bind:value={articleText}
      ></textarea>

      {#if textInfo}
        <div class="mt-3 p-3 bg-green-50 rounded-lg text-xs text-green-800">
          Rozparsovano: {textInfo.headline ? `"${textInfo.headline.slice(0, 60)}..."` : 'bez headline'} &middot;
          {textInfo.total_chars} znaku &middot;
          {textInfo.estimated_spreads || '?'} spreadu &middot;
          {textInfo.pull_quotes || 0} pull quotes
        </div>
      {/if}

      <div class="flex gap-3 mt-4">
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 2; }}>
          &larr; Zpet
        </button>
        <button
          class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={!articleText.trim() || textUploading}
          onclick={uploadText}
        >
          {#if textUploading}
            <span class="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
            Nahrazuji...
          {:else}
            Pokracovat &rarr;
          {/if}
        </button>
      </div>
    </div>

  <!-- STEP 4: Nastaveni -->
  {:else if step === 4}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Nastaveni layoutu</h2>

      <!-- Pocet stran -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">Pocet stran</label>
        <div class="flex gap-2">
          <button
            class="px-4 py-2 rounded-lg border text-sm transition-colors
                   {numPages === 'auto' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
            onclick={() => { numPages = 'auto'; }}
          >Auto</button>
          {#each [4, 6, 8, 10, 12] as n}
            <button
              class="px-4 py-2 rounded-lg border text-sm transition-colors
                     {numPages === n ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
              onclick={() => { numPages = n; }}
            >{n}</button>
          {/each}
        </div>
      </div>

      <!-- AI rezim -->
      <div class="mb-6">
        <label class="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" bind:checked={useAi} class="w-4 h-4 text-indigo-600 rounded" />
          <div>
            <div class="text-sm font-medium text-gray-700">AI-assisted planovani</div>
            <div class="text-xs text-gray-500">Claude navrhnne optimalni kompozici (vyzaduje API klic)</div>
          </div>
        </label>
      </div>

      <!-- Souhrn -->
      <div class="p-4 bg-gray-50 rounded-lg mb-6 text-xs text-gray-600 space-y-1">
        <div>Styl: <strong>{selectedStyle}</strong></div>
        <div>Fotky: <strong>{uploadedImages.length}</strong></div>
        {#if textInfo}
          <div>Text: <strong>{textInfo.total_chars} znaku</strong>, odhad <strong>{textInfo.estimated_spreads || '?'} spreadu</strong></div>
        {/if}
        <div>Strany: <strong>{numPages}</strong></div>
      </div>

      <div class="flex gap-3">
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 3; }}>
          &larr; Zpet
        </button>
        <button
          class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
          disabled={planning}
          onclick={runPlanning}
        >
          {#if planning}
            <span class="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
            {planMessage}
          {:else}
            Naplanovat layout &rarr;
          {/if}
        </button>
      </div>
    </div>

  <!-- STEP 5: Plan preview -->
  {:else if step === 5}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Nahled planu</h2>

      {#if planResult}
        <div class="mb-4 p-3 bg-indigo-50 rounded-lg text-sm text-indigo-800">
          {planResult.total_pages || '?'} stran, {planResult.spreads?.length || '?'} spreadu
        </div>

        <!-- Miniaturky spreadu -->
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {#each planResult.spreads || [] as spread, idx}
            <div class="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div class="text-xs font-bold text-gray-700 mb-1">Spread {idx + 1}</div>
              <div class="text-xs text-gray-500 mb-2">{spread.spread_type || spread.pattern_id || '?'}</div>

              <!-- Zjednodusena miniatura -->
              <div class="relative bg-white border border-gray-300 rounded" style="aspect-ratio: 2/1.44;">
                {#each spread.slots || [] as slot, si}
                  {@const l = slot.x != null ? (slot.x / 990 * 100) : (si * 25)}
                  {@const t = slot.y != null ? (slot.y / 720 * 100) : 10}
                  {@const w = slot.width != null ? (slot.width / 990 * 100) : 20}
                  {@const h = slot.height != null ? (slot.height / 720 * 100) : 30}
                  <div
                    class="absolute rounded-sm text-[8px] flex items-center justify-center
                           {slot.slot_type === 'image' || slot.frame_type === 'image'
                             ? 'bg-green-200 border border-green-400 text-green-700'
                             : 'bg-blue-200 border border-blue-400 text-blue-700'}"
                    style="left:{l}%; top:{t}%; width:{w}%; height:{h}%;"
                  >
                    {slot.slot_type?.[0]?.toUpperCase() || slot.frame_type?.[0]?.toUpperCase() || '?'}
                  </div>
                {/each}
              </div>

              {#if spread.assigned_images?.length}
                <div class="text-[10px] text-gray-400 mt-1">{spread.assigned_images.length} fotek</div>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="text-center py-8 text-gray-400 text-sm">Plan neni k dispozici</div>
      {/if}

      <div class="flex gap-3">
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 4; }}>
          &larr; Zpet
        </button>
        <button
          class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
          disabled={!planResult || generating}
          onclick={() => { step = 6; runGenerate(); }}
        >
          Generovat IDML &rarr;
        </button>
      </div>
    </div>

  <!-- STEP 6: Generovani -->
  {:else if step === 6}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Generovani IDML</h2>

      {#if generating}
        <div class="text-center py-10">
          <div class="animate-spin inline-block w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full mb-4"></div>
          <p class="text-indigo-700 font-medium">{generateMessage}</p>
        </div>
      {:else if generateResult}
        <div class="text-center py-8">
          <div class="text-4xl mb-3">&#x2705;</div>
          <p class="text-lg font-bold text-gray-900 mb-2">IDML vygenerovan!</p>
          <p class="text-sm text-gray-500 mb-6">
            {generateResult.size_kb || '?'} KB
          </p>
          <button
            class="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors text-sm"
            onclick={downloadIdml}
          >
            Stahnout IDML
          </button>
        </div>
      {:else}
        <div class="text-center py-8 text-gray-400 text-sm">
          <p>Klikni "Generovat" v predchozim kroku</p>
        </div>
      {/if}

      <div class="flex gap-3 mt-4">
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 5; }}>
          &larr; Zpet k planu
        </button>
        <button
          class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm"
          onclick={() => navigate('dashboard')}
        >
          Na dashboard
        </button>
      </div>
    </div>
  {/if}
</div>
