<script>
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';
  import { navigate } from '../stores/router.js';
  import SpreadPreview from '../components/SpreadPreview.svelte';

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
  let batchMode = $state(false);  // Session 8: Batch generování

  // Step 5: Plan preview (Session 7 — detailní preview)
  let planResult = $state(null);
  let planDetail = $state(null);      // z plan-detail API (se sloty)
  let planning = $state(false);
  let planMessage = $state('');
  let selectedSpreadIdx = $state(null);
  let selectedSlot = $state(null);     // detail vybraného slotu
  let draggedImage = $state(null);     // filename přetahované fotky
  let updatingPlan = $state(false);

  // Step 6: Generate
  let generating = $state(false);
  let generateMessage = $state('');
  let generateResult = $state(null);

  // Validation
  let validation = $state(null);

  // Session 8: Style Transfer
  let importingStyle = $state(false);

  // Session 8: Batch generování
  let batchPlans = $state(null);        // {variants: [...]}
  let batchVariantIdx = $state(0);      // aktuální varianta v náhledu
  let batchGenerating = $state(false);
  let batchProgress = $state(null);
  let batchResults = $state(null);

  // Session 8: PDF Preview
  let generatingPdf = $state(false);
  let pdfReady = $state(false);

  // Session 8: Caption Matching
  let matchingCaptions = $state(false);
  let captionMatches = $state(null);

  // Session 11: Maps / Illustrator Integration
  let detectedMaps = $state([]);
  let detectingMaps = $state(false);
  let exportingMap = $state(false);
  let importingMap = $state(false);
  let mapPanelOpen = $state(false);

  // Session 10: Multi-Article
  let multiArticleMode = $state(false);
  let articleFiles = $state([]);         // File[] pro multi-article upload
  let multiArticleText = $state('');     // Text s delimitery
  let articlesInfo = $state(null);       // Parsovaný výsledek z API
  let imageAllocation = $state({});      // {article_id: [filename...]}
  let multiPlanResult = $state(null);
  let multiPlanMessage = $state('');
  let multiPlanning = $state(false);
  let multiGenerating = $state(false);
  let multiGenerateMessage = $state('');
  let multiGenerateResult = $state(null);

  const STEPS = [
    { num: 1, label: 'Styl' },
    { num: 2, label: 'Fotky' },
    { num: 3, label: 'Text' },
    { num: 4, label: 'Nastaveni' },
    { num: 5, label: 'Nahled' },
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
        else if (projectMeta.plan) { step = 5; loadPlanDetail(); }
        else if (projectMeta.article) step = 4;
        else if (uploadedImages.length) step = 3;
        else step = 1;
      } catch (e) {
        notify('Chyba: ' + e.message, 'error');
      }
    }
  }
  init();

  // === Validace ===
  async function runValidation() {
    if (!createdProjectId) return;
    try {
      validation = await api.layoutValidate(createdProjectId);
    } catch (e) {
      // Tichá chyba
    }
  }

  // === Plan detail (Session 7) ===
  async function loadPlanDetail() {
    if (!createdProjectId) return;
    try {
      planDetail = await api.layoutPlanDetail(createdProjectId);
    } catch (e) {
      // Fallback — zůstaneme u planResult
      planDetail = null;
    }
  }

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
      runValidation();
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      textUploading = false;
    }
  }

  // === Multi-Article: Upload článků ===
  function handleArticleFilesSelect(e) {
    const files = Array.from(e.target.files || []);
    articleFiles = [...articleFiles, ...files.filter(f => f.name.endsWith('.txt') || f.name.endsWith('.md'))];
    e.target.value = '';
  }

  async function uploadMultiArticles() {
    if (!createdProjectId) return;
    textUploading = true;
    try {
      let result;
      if (articleFiles.length > 0) {
        result = await api.layoutMultiUploadArticles(createdProjectId, { files: articleFiles });
      } else if (multiArticleText.trim()) {
        result = await api.layoutMultiUploadArticles(createdProjectId, { text: multiArticleText });
      } else {
        return;
      }
      articlesInfo = result;
      // Inicializovat prázdnou alokaci
      imageAllocation = {};
      for (const a of result.articles) {
        imageAllocation[a.article_id] = [];
      }
      notify(`${result.article_count} článků nahráno`, 'success');
      step = 4;
      runValidation();
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      textUploading = false;
    }
  }

  // === Multi-Article: Image Allocation ===
  function allocateImageToArticle(filename, articleId) {
    // Odebrat z jiných článků
    const newAlloc = { ...imageAllocation };
    for (const key of Object.keys(newAlloc)) {
      newAlloc[key] = newAlloc[key].filter(fn => fn !== filename);
    }
    if (!newAlloc[articleId]) newAlloc[articleId] = [];
    newAlloc[articleId] = [...newAlloc[articleId], filename];
    imageAllocation = newAlloc;
  }

  async function saveImageAllocation() {
    if (!createdProjectId) return;
    try {
      const result = await api.layoutMultiAllocateImages(createdProjectId, imageAllocation);
      imageAllocation = result.allocation;
      notify(`Alokace uložena (${result.auto_assigned} auto-přiřazeno)`, 'success');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  // === Multi-Article: Planning ===
  async function runMultiPlanning() {
    if (!createdProjectId) return;
    multiPlanning = true;
    multiPlanMessage = 'Spouštím multi-article plánování...';
    multiPlanResult = null;

    try {
      await saveImageAllocation();
      await api.layoutMultiPlan(createdProjectId, { use_ai: useAi });

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1000));
        const prog = await api.layoutMultiPlanProgress(createdProjectId);
        multiPlanMessage = prog.message || '';
        if (prog.status === 'done') {
          multiPlanResult = prog.result;
          done = true;
          step = 5;
        } else if (prog.status === 'error') {
          notify('Chyba plánování: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      multiPlanning = false;
    }
  }

  // === Multi-Article: Generate IDML ===
  async function runMultiGenerate() {
    if (!createdProjectId) return;
    multiGenerating = true;
    multiGenerateMessage = 'Generuji multi-article IDML...';
    multiGenerateResult = null;

    try {
      await api.layoutMultiGenerate(createdProjectId);

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1500));
        const prog = await api.layoutMultiGenerateProgress(createdProjectId);
        multiGenerateMessage = prog.message || '';
        if (prog.status === 'done') {
          multiGenerateResult = prog.result;
          done = true;
          notify('Multi-article IDML vygenerován!', 'success');
        } else if (prog.status === 'error') {
          notify('Chyba generování: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      multiGenerating = false;
    }
  }

  // === Step 4: Nastaveni → Step 5: Plan ===
  async function runPlanning() {
    if (!createdProjectId) return;

    // Batch mode
    if (batchMode) {
      return runBatchPlanning();
    }

    planning = true;
    planMessage = 'Spoustim planovani...';
    planResult = null;
    planDetail = null;

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
          loadPlanDetail();
          runValidation();
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

  // === Step 5: Drag & drop editace plánu ===
  function handleSpreadSelect(spread) {
    selectedSpreadIdx = spread.spread_index;
    selectedSlot = null;
  }

  function handleSlotClick(detail) {
    selectedSlot = detail;
  }

  function handleImageDragStart(imgFilename) {
    draggedImage = imgFilename;
  }

  function handleImageDragEnd() {
    draggedImage = null;
  }

  async function handleImageDropOnSlot(detail) {
    if (!createdProjectId || updatingPlan) return;
    updatingPlan = true;
    try {
      // Zjistit, z jakého spreadu fotka pochází
      const fromSpread = planDetail?.spreads?.findIndex(s =>
        s.assigned_images?.some(img => img.filename === detail.image)
      ) ?? -1;

      if (fromSpread >= 0) {
        await api.layoutUpdatePlan(createdProjectId, {
          move_image_to_spread: {
            image: detail.image,
            from_spread: fromSpread,
            to_spread: detail.spread.spread_index,
          }
        });
      }
      await loadPlanDetail();
      notify('Fotka presunuta', 'success');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      updatingPlan = false;
    }
  }

  async function moveSpread(from, to) {
    if (!createdProjectId || !planDetail || updatingPlan) return;
    const count = planDetail.spreads.length;
    if (to < 0 || to >= count) return;
    updatingPlan = true;
    try {
      const order = Array.from({ length: count }, (_, i) => i);
      [order[from], order[to]] = [order[to], order[from]];
      const result = await api.layoutUpdatePlan(createdProjectId, { spread_order: order });
      planResult = result.plan;
      await loadPlanDetail();
      selectedSpreadIdx = to;
      notify('Spread presunut', 'success');
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      updatingPlan = false;
    }
  }

  // === Step 6: Generate ===
  async function runGenerate() {
    if (!createdProjectId) return;

    // Batch mode — generuj všechny varianty
    if (batchMode && batchPlans) {
      return runBatchGenerate();
    }

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

  // === Session 8: Style Transfer ===
  async function importStyleFromIdml(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    importingStyle = true;
    try {
      const result = await api.layoutCreateStyleFromTemplate(file);
      notify(`Styl "${result.profile_name}" importovan`, 'success');
      // Reload templates
      const data = await api.layoutTemplates();
      templates = data.profiles || [];
      selectedStyle = result.profile_id;
    } catch (e) {
      notify('Import stylu selhal: ' + e.message, 'error');
    } finally {
      importingStyle = false;
    }
  }

  async function deleteCustomStyle(profileId) {
    try {
      await api.layoutDeleteTemplate(profileId);
      notify('Styl smazan', 'success');
      const data = await api.layoutTemplates();
      templates = data.profiles || [];
      if (selectedStyle === profileId) selectedStyle = 'ng_feature';
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    }
  }

  // === Session 8: Batch generování ===
  async function runBatchPlanning() {
    if (!createdProjectId) return;
    planning = true;
    planMessage = 'Generuji varianty...';
    batchPlans = null;

    try {
      const result = await api.layoutBatchPlan(createdProjectId, {
        num_pages: numPages,
        style_profile: selectedStyle,
        variant_count: 3,
      });
      batchPlans = result;
      // Načíst detail prvního plánu (uložen jako hlavní)
      planResult = result.plans?.[0];
      step = 5;
      loadPlanDetail();
      runValidation();
      notify(`${result.variants} varianty naplanovany`, 'success');
    } catch (e) {
      notify('Chyba batch planovani: ' + e.message, 'error');
    } finally {
      planning = false;
    }
  }

  async function runBatchGenerate() {
    batchGenerating = true;
    batchProgress = { completed: 0, total: 3 };
    batchResults = null;
    generateMessage = 'Generuji varianty IDML...';

    try {
      await api.layoutBatchGenerate(createdProjectId);

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1500));
        const prog = await api.layoutBatchGenerateProgress(createdProjectId);
        batchProgress = prog;
        generateMessage = prog.message || '';
        if (prog.status === 'done') {
          batchResults = prog.result;
          done = true;
        } else if (prog.status === 'error') {
          notify('Chyba: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      batchGenerating = false;
    }
  }

  function downloadBatchVariant(variant) {
    if (!createdProjectId) return;
    window.open(api.layoutBatchDownloadUrl(createdProjectId, variant), '_blank');
  }

  // === Session 8: PDF Preview ===
  async function generatePdfPreview() {
    if (!createdProjectId) return;
    generatingPdf = true;
    pdfReady = false;
    try {
      await api.layoutGeneratePreviewPdf(createdProjectId);
      pdfReady = true;
      notify('PDF nahled vygenerovan', 'success');
    } catch (e) {
      notify('PDF preview selhal: ' + e.message, 'error');
    } finally {
      generatingPdf = false;
    }
  }

  function openPdfPreview() {
    if (!createdProjectId) return;
    window.open(api.layoutPreviewPdfUrl(createdProjectId), '_blank');
  }

  // === Session 8: Caption Matching ===
  async function runCaptionMatching() {
    if (!createdProjectId) return;
    matchingCaptions = true;
    captionMatches = null;
    try {
      await api.layoutMatchCaptions(createdProjectId);

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 1500));
        const prog = await api.layoutMatchCaptionsProgress(createdProjectId);
        if (prog.status === 'done') {
          captionMatches = prog.result?.matches || [];
          done = true;
          notify(`${captionMatches.length} popisku prirazeno`, 'success');
        } else if (prog.status === 'error') {
          notify('Caption matching selhal: ' + prog.message, 'error');
          done = true;
        }
      }
    } catch (e) {
      notify('Chyba: ' + e.message, 'error');
    } finally {
      matchingCaptions = false;
    }
  }

  // === Session 11: Map detection & Illustrator workflow ===

  async function detectMaps() {
    if (!createdProjectId) return;
    detectingMaps = true;
    try {
      const res = await api.layoutDetectMaps(createdProjectId);
      detectedMaps = res.maps || [];
      if (detectedMaps.length > 0) {
        mapPanelOpen = true;
        notify(`${detectedMaps.length} map/infografik detekováno`, 'success');
      } else {
        notify('Žádné mapy nenalezeny', 'info');
      }
    } catch (e) {
      notify('Chyba detekce map: ' + e.message, 'error');
    } finally {
      detectingMaps = false;
    }
  }

  async function exportMapTemplate(map) {
    if (!createdProjectId) return;
    exportingMap = true;
    try {
      const res = await api.layoutExportMapTemplate(createdProjectId, {
        slot_id: map.filename?.replace(/\.[^.]+$/, '') || 'map_0',
        width: map.width ? Math.min(map.width * 0.72, 600) : 400,
        height: map.height ? Math.min(map.height * 0.72, 600) : 400,
        label_text: '',
        bleed: 8.5,
      });
      if (res.status === 'ok') {
        notify(res.message, 'success');
      } else {
        notify(res.detail || 'Chyba exportu', 'error');
      }
    } catch (e) {
      notify('Illustrator nepřipojený: ' + e.message, 'error');
    } finally {
      exportingMap = false;
    }
  }

  async function importEditedMap(slotId) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.png,.jpg,.jpeg,.tif,.tiff,.pdf';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      importingMap = true;
      try {
        const res = await api.layoutImportEditedMap(createdProjectId, slotId, file);
        if (res.status === 'ok') {
          notify(res.message, 'success');
          // Refresh maps
          const mapsRes = await api.layoutListMaps(createdProjectId);
          detectedMaps = mapsRes.maps || [];
        } else {
          notify(res.detail || 'Chyba importu', 'error');
        }
      } catch (e) {
        notify('Chyba importu mapy: ' + e.message, 'error');
      } finally {
        importingMap = false;
      }
    };
    input.click();
  }

  // Keyboard shortcuts
  function handleKeydown(e) {
    // Escape = zpet
    if (e.key === 'Escape' && step > 1) {
      step = step - 1;
      if (step === 5) loadPlanDetail();
    }
    // Enter = dal krok (pokud neni v textarea)
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'INPUT') {
      if (step === 1) createProject();
    }
    // Arrow keys v step 5 — navigace spreadu
    if (step === 5 && planDetail?.spreads) {
      const count = planDetail.spreads.length;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        selectedSpreadIdx = selectedSpreadIdx != null ? Math.min(selectedSpreadIdx + 1, count - 1) : 0;
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        selectedSpreadIdx = selectedSpreadIdx != null ? Math.max(selectedSpreadIdx - 1, 0) : 0;
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="max-w-5xl mx-auto">
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

  <!-- Validation warnings (zobrazí se od step 4+) -->
  {#if validation && step >= 4}
    {#if validation.errors?.length > 0}
      <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
        {#each validation.errors as err}
          <div class="text-sm text-red-700 flex items-center gap-2">
            <span class="text-red-500 font-bold">!</span> {err.message}
          </div>
        {/each}
      </div>
    {/if}
    {#if validation.warnings?.length > 0}
      <div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-1">
        {#each validation.warnings as warn}
          <div class="text-xs text-amber-700 flex items-center gap-2">
            <span class="text-amber-500">&#x26A0;</span> {warn.message}
          </div>
        {/each}
      </div>
    {/if}
  {/if}

  <!-- STEP 1: Styl -->
  {#if step === 1}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Zvol styl layoutu</h2>

      <div class="space-y-3 mb-6">
        {#if templates.length > 0}
          {#each templates as tpl}
            <div class="relative">
              <button
                class="w-full text-left p-4 rounded-lg border-2 transition-colors
                       {selectedStyle === tpl.id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}"
                onclick={() => { selectedStyle = tpl.id; }}
              >
                <div class="font-medium text-gray-900">
                  {tpl.name}
                  {#if tpl.id.startsWith('custom_')}
                    <span class="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded ml-2">Custom</span>
                  {/if}
                </div>
                <div class="text-xs text-gray-500 mt-1">{tpl.page_width} x {tpl.page_height} pt, {tpl.columns} sloupcu</div>
              </button>
              {#if tpl.id.startsWith('custom_')}
                <button
                  class="absolute top-2 right-2 w-6 h-6 text-gray-400 hover:text-red-500 text-sm"
                  onclick={(e) => { e.stopPropagation(); deleteCustomStyle(tpl.id); }}
                  title="Smazat custom styl"
                >&times;</button>
              {/if}
            </div>
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

      <!-- Session 8: Import stylu z IDML -->
      <div class="border-t border-gray-100 pt-4 mb-6">
        <label class="inline-flex items-center gap-2 px-4 py-2 bg-gray-50 text-gray-700 rounded-lg cursor-pointer hover:bg-gray-100 text-xs font-medium transition-colors border border-gray-200">
          {#if importingStyle}
            <span class="animate-spin inline-block w-3 h-3 border-2 border-gray-500 border-t-transparent rounded-full"></span>
            Importuji styl...
          {:else}
            Importovat styl z IDML
          {/if}
          <input type="file" accept=".idml" onchange={importStyleFromIdml} class="hidden" disabled={importingStyle} />
        </label>
        <p class="text-[10px] text-gray-400 mt-1">Nahraj libovolny IDML soubor — automaticky se extrahuje typograficky profil</p>
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
      <!-- Multi-article toggle -->
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-gray-900">
          {multiArticleMode ? 'Multi-article layout' : 'Vloz text clanku'}
        </h2>
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={multiArticleMode}
            class="w-4 h-4 text-indigo-600 rounded" />
          <span class="text-xs font-medium text-gray-600">Multi-article</span>
        </label>
      </div>

      {#if !multiArticleMode}
        <!-- Single article mode (original) -->
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

      {:else}
        <!-- Multi-article mode -->
        <p class="text-xs text-gray-500 mb-4">
          Nahraj N souborů (1 soubor = 1 článek) nebo vlož text s oddělovači <code>===</code> / <code># ARTICLE: Název</code>.
        </p>

        <div class="mb-3 flex gap-2">
          <label class="inline-block px-3 py-1.5 bg-gray-100 text-gray-700 rounded cursor-pointer hover:bg-gray-200 text-xs font-medium transition-colors">
            Nahrat .txt soubory
            <input type="file" accept=".txt,.md" multiple onchange={handleArticleFilesSelect} class="hidden" />
          </label>
          {#if articleFiles.length > 0}
            <span class="text-xs text-gray-500 self-center">{articleFiles.length} souborů vybráno</span>
          {/if}
        </div>

        {#if articleFiles.length === 0}
          <textarea
            class="w-full h-48 p-3 border border-gray-300 rounded-lg text-sm font-mono resize-y focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400"
            placeholder="# ARTICLE: Prvni clanek
# HEADLINE: Nazev prvniho clanku
Text prvniho clanku...

===

# ARTICLE: Druhy clanek
# HEADLINE: Nazev druheho clanku
Text druheho clanku..."
            bind:value={multiArticleText}
          ></textarea>
        {:else}
          <div class="space-y-1 mb-3">
            {#each articleFiles as f, i}
              <div class="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded text-xs">
                <span class="text-gray-700">{f.name}</span>
                <span class="text-gray-400">{(f.size / 1024).toFixed(1)} KB</span>
                <button class="ml-auto text-red-400 hover:text-red-600" onclick={() => { articleFiles = articleFiles.filter((_, j) => j !== i); }}>x</button>
              </div>
            {/each}
          </div>
        {/if}

        {#if articlesInfo}
          <div class="mt-3 p-3 bg-green-50 rounded-lg text-xs text-green-800">
            {articlesInfo.article_count} článků:
            {#each articlesInfo.articles as a, i}
              <span class="inline-block mr-2">
                {i + 1}. {a.headline || a.article_id} ({a.total_chars} zn.)
              </span>
            {/each}
          </div>
        {/if}

        <div class="flex gap-3 mt-4">
          <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 2; }}>
            &larr; Zpet
          </button>
          <button
            class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={(articleFiles.length === 0 && !multiArticleText.trim()) || textUploading}
            onclick={uploadMultiArticles}
          >
            {#if textUploading}
              <span class="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
              Nahravani...
            {:else}
              Pokracovat &rarr;
            {/if}
          </button>
        </div>
      {/if}
    </div>

  <!-- STEP 4: Nastaveni -->
  {:else if step === 4}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Nastaveni layoutu</h2>

      <!-- Pocet stran -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">Pocet stran</label>
        <div class="flex gap-2 flex-wrap">
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
      <div class="mb-4">
        <label class="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" bind:checked={useAi} class="w-4 h-4 text-indigo-600 rounded" />
          <div>
            <div class="text-sm font-medium text-gray-700">AI-assisted planovani</div>
            <div class="text-xs text-gray-500">Claude navrhnne optimalni kompozici (vyzaduje API klic)</div>
          </div>
        </label>
      </div>

      <!-- Batch mode (Session 8) -->
      <div class="mb-6">
        <label class="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" bind:checked={batchMode} class="w-4 h-4 text-purple-600 rounded" />
          <div>
            <div class="text-sm font-medium text-gray-700">Batch — generovat 3 varianty</div>
            <div class="text-xs text-gray-500">Ruzne rozlozeni fotek v kazde variante pro porovnani</div>
          </div>
        </label>
      </div>

      <!-- Multi-article: Image Allocation -->
      {#if multiArticleMode && articlesInfo}
        <div class="mb-6">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">Alokace fotek k clankum</h3>
          <p class="text-xs text-gray-500 mb-3">Prirad fotky k jednotlivym clankum. Neprirazene se automaticky rozdeli.</p>
          <div class="space-y-3">
            {#each articlesInfo.articles as article}
              <div class="p-3 bg-gray-50 rounded-lg">
                <div class="text-xs font-medium text-gray-700 mb-2">
                  {article.headline || article.article_id}
                  <span class="text-gray-400 ml-1">({article.total_chars} zn.)</span>
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each (imageAllocation[article.article_id] || []) as fn}
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs">
                      {fn}
                      <button class="text-indigo-400 hover:text-indigo-600" onclick={() => {
                        imageAllocation[article.article_id] = imageAllocation[article.article_id].filter(f => f !== fn);
                        imageAllocation = { ...imageAllocation };
                      }}>x</button>
                    </span>
                  {/each}
                  <select class="text-xs border border-gray-200 rounded px-1 py-0.5"
                    onchange={(e) => { if (e.target.value) { allocateImageToArticle(e.target.value, article.article_id); e.target.value = ''; } }}>
                    <option value="">+ pridat fotku</option>
                    {#each uploadedImages as img}
                      {#if !Object.values(imageAllocation).flat().includes(img.filename)}
                        <option value={img.filename}>{img.filename}</option>
                      {/if}
                    {/each}
                  </select>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Souhrn -->
      <div class="p-4 bg-gray-50 rounded-lg mb-6 text-xs text-gray-600 space-y-1">
        <div>Styl: <strong>{selectedStyle}</strong></div>
        <div>Fotky: <strong>{uploadedImages.length}</strong></div>
        {#if multiArticleMode && articlesInfo}
          <div>Clanky: <strong>{articlesInfo.article_count}</strong></div>
        {:else if textInfo}
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
          disabled={planning || multiPlanning}
          onclick={multiArticleMode ? runMultiPlanning : runPlanning}
        >
          {#if planning || multiPlanning}
            <span class="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
            {multiArticleMode ? multiPlanMessage : planMessage}
          {:else}
            Naplanovat layout &rarr;
          {/if}
        </button>
      </div>
    </div>

  <!-- STEP 5: Plan preview — Session 7 nový design -->
  {:else if step === 5}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <!-- Multi-article boundaries -->
      {#if multiArticleMode && multiPlanResult?.boundaries}
        <div class="mb-4 p-3 bg-purple-50 rounded-lg">
          <h3 class="text-xs font-semibold text-purple-700 mb-2">Multi-article layout — {multiPlanResult.article_count} clanku, {multiPlanResult.total_pages} stran</h3>
          <div class="space-y-1">
            {#each multiPlanResult.boundaries as b, i}
              <div class="flex items-center gap-2 text-xs">
                <span class="w-5 h-5 rounded-full bg-purple-200 text-purple-700 flex items-center justify-center text-[10px] font-bold">{i + 1}</span>
                <span class="font-medium text-gray-700">{b.headline || b.article_id}</span>
                <span class="text-gray-400">str. {b.start_page}–{b.end_page} ({b.spread_count} spreadu)</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-gray-900">Nahled planu</h2>
        {#if planResult || planDetail}
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span class="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded font-medium">
              {planDetail?.total_pages || planResult?.total_pages || '?'} stran
            </span>
            <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {planDetail?.spreads?.length || planResult?.spreads?.length || '?'} spreadu
            </span>
          </div>
        {/if}
      </div>

      <!-- Session 8: Toolbar — PDF Preview + Caption Matching + Batch tabs -->
      <div class="flex items-center gap-2 mb-4 flex-wrap">
        <!-- PDF Preview -->
        <button
          class="px-3 py-1.5 text-xs border rounded-lg transition-colors
                 {generatingPdf ? 'border-gray-300 text-gray-400' : 'border-gray-200 text-gray-600 hover:border-indigo-400 hover:text-indigo-600'}"
          disabled={generatingPdf || !planDetail}
          onclick={generatePdfPreview}
        >
          {#if generatingPdf}
            <span class="animate-spin inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full mr-1"></span>
            Generuji PDF...
          {:else}
            PDF nahled
          {/if}
        </button>
        {#if pdfReady}
          <button
            class="px-3 py-1.5 text-xs border border-green-300 text-green-700 rounded-lg hover:bg-green-50 transition-colors"
            onclick={openPdfPreview}
          >
            Otevrit PDF
          </button>
        {/if}

        <!-- Caption Matching -->
        {#if textInfo && (textInfo.captions > 0 || projectMeta?.article?.captions?.length > 0)}
          <button
            class="px-3 py-1.5 text-xs border rounded-lg transition-colors
                   {matchingCaptions ? 'border-gray-300 text-gray-400' : 'border-gray-200 text-gray-600 hover:border-cyan-400 hover:text-cyan-600'}"
            disabled={matchingCaptions}
            onclick={runCaptionMatching}
          >
            {#if matchingCaptions}
              <span class="animate-spin inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full mr-1"></span>
              Prirazuji popisky...
            {:else}
              Prirazit popisky k fotkam
            {/if}
          </button>
        {/if}

        <!-- Map Detection (Session 11) -->
        <button
          class="px-3 py-1.5 text-xs border rounded-lg transition-colors
                 {detectingMaps ? 'border-gray-300 text-gray-400' : 'border-gray-200 text-gray-600 hover:border-amber-400 hover:text-amber-600'}"
          disabled={detectingMaps}
          onclick={detectMaps}
        >
          {#if detectingMaps}
            <span class="animate-spin inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full mr-1"></span>
            Hledam mapy...
          {:else}
            Detekovat mapy
          {/if}
        </button>
        {#if detectedMaps.length > 0}
          <button
            class="px-3 py-1.5 text-xs border rounded-lg transition-colors
                   {mapPanelOpen ? 'bg-amber-100 text-amber-700 border-amber-300' : 'border-amber-200 text-amber-600 hover:bg-amber-50'}"
            onclick={() => { mapPanelOpen = !mapPanelOpen; }}
          >
            Mapy ({detectedMaps.length})
          </button>
        {/if}

        <!-- Batch variant tabs -->
        {#if batchMode && batchPlans}
          <div class="flex-1"></div>
          <div class="flex gap-1">
            {#each Array(batchPlans.variants || 3) as _, vi}
              <button
                class="px-3 py-1.5 text-xs rounded-lg transition-colors
                       {batchVariantIdx === vi ? 'bg-purple-100 text-purple-700 border border-purple-300' : 'border border-gray-200 text-gray-500 hover:border-purple-300'}"
                onclick={() => { batchVariantIdx = vi; }}
              >
                V{vi + 1}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Caption Matches Display -->
      {#if captionMatches && captionMatches.length > 0}
        <div class="mb-4 p-3 bg-cyan-50 border border-cyan-200 rounded-lg">
          <div class="text-xs font-medium text-cyan-800 mb-2">Prirazene popisky ({captionMatches.length})</div>
          <div class="space-y-1.5 max-h-32 overflow-y-auto">
            {#each captionMatches as match}
              {#if match.caption}
                <div class="flex items-start gap-2 text-[11px]">
                  <span class="text-cyan-600 font-medium whitespace-nowrap">{match.image}:</span>
                  <span class="text-gray-700">{match.caption.slice(0, 100)}{match.caption.length > 100 ? '...' : ''}</span>
                  <span class="text-gray-400 whitespace-nowrap">{match.method === 'ai' ? `(AI ${Math.round(match.confidence * 100)}%)` : '(poradi)'}</span>
                </div>
              {/if}
            {/each}
          </div>
        </div>
      {/if}

      <!-- Map Panel (Session 11) -->
      {#if mapPanelOpen && detectedMaps.length > 0}
        <div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <div class="text-xs font-medium text-amber-800">Detekovane mapy/infografiky ({detectedMaps.length})</div>
            <button class="text-gray-400 hover:text-gray-600 text-xs" onclick={() => { mapPanelOpen = false; }}>Zavrit</button>
          </div>
          <div class="space-y-2 max-h-48 overflow-y-auto">
            {#each detectedMaps as map, mi}
              <div class="flex items-center gap-3 p-2 bg-white rounded border border-amber-100">
                <div class="w-12 h-12 bg-amber-100 rounded flex items-center justify-center text-amber-600 text-lg font-bold flex-shrink-0">
                  {map.map_type === 'map' ? 'M' : map.map_type === 'infographic' ? 'I' : 'D'}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium text-gray-800 truncate">{map.filename}</div>
                  <div class="text-[10px] text-gray-500">
                    {map.map_type} &middot; {Math.round(map.confidence * 100)}% &middot;
                    {map.width}&times;{map.height}px
                  </div>
                  {#if map.reasons?.length}
                    <div class="text-[9px] text-amber-600 truncate">{map.reasons.join(', ')}</div>
                  {/if}
                </div>
                <div class="flex flex-col gap-1 flex-shrink-0">
                  {#if map.status === 'edited'}
                    <span class="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded">Editovano</span>
                  {:else}
                    <button
                      class="px-2 py-1 text-[10px] bg-amber-100 text-amber-700 rounded hover:bg-amber-200 transition-colors disabled:opacity-50"
                      disabled={exportingMap}
                      onclick={() => exportMapTemplate(map)}
                    >
                      {exportingMap ? '...' : 'Do Illustratoru'}
                    </button>
                  {/if}
                  <button
                    class="px-2 py-1 text-[10px] bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                    disabled={importingMap}
                    onclick={() => importEditedMap(map.filename?.replace(/\.[^.]+$/, '') || `map_${mi}`)}
                  >
                    {importingMap ? '...' : 'Import mapy'}
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if planDetail?.spreads}
        <!-- Hlavní layout: spreads grid + detail panel -->
        <div class="flex gap-4 mb-6" style="min-height: 400px;">
          <!-- Levý panel: Spread miniaturky se řazením -->
          <div class="w-2/3 space-y-3">
            <div class="flex items-center justify-between text-xs text-gray-500 mb-2">
              <span>Klikni na spread pro detail, pretahni fotky mezi spready</span>
              <span class="text-gray-400">Sipky: navigace</span>
            </div>

            <div class="grid grid-cols-2 gap-3">
              {#each planDetail.spreads as spread, idx}
                <div class="relative">
                  <!-- Spread reorder tlačítka -->
                  <div class="absolute -left-6 top-1/2 -translate-y-1/2 flex flex-col gap-1 z-10">
                    <button
                      class="w-5 h-5 bg-gray-100 hover:bg-gray-200 rounded text-xs text-gray-500 disabled:opacity-30"
                      disabled={idx === 0 || updatingPlan}
                      onclick={() => moveSpread(idx, idx - 1)}
                      title="Posunout nahoru"
                    >&#x25B2;</button>
                    <button
                      class="w-5 h-5 bg-gray-100 hover:bg-gray-200 rounded text-xs text-gray-500 disabled:opacity-30"
                      disabled={idx === planDetail.spreads.length - 1 || updatingPlan}
                      onclick={() => moveSpread(idx, idx + 1)}
                      title="Posunout dolu"
                    >&#x25BC;</button>
                  </div>

                  <!-- Spread číslo -->
                  <div class="text-[10px] text-gray-400 mb-1 ml-1">
                    Spread {idx + 1}
                    {#if spread.assigned_images?.length}
                      &middot; {spread.assigned_images.length} fotek
                    {/if}
                  </div>

                  <SpreadPreview
                    {spread}
                    projectId={createdProjectId}
                    width={380}
                    selected={selectedSpreadIdx === idx}
                    onSelect={handleSpreadSelect}
                    onSlotClick={handleSlotClick}
                    onImageDrop={handleImageDropOnSlot}
                    {draggedImage}
                  />
                </div>
              {/each}
            </div>
          </div>

          <!-- Pravý panel: Detail vybraného spreadu / slotu -->
          <div class="w-1/3 border-l border-gray-200 pl-4">
            {#if selectedSlot}
              <!-- Detail vybraného slotu -->
              <div class="space-y-3">
                <h3 class="text-sm font-bold text-gray-800">
                  Slot: {selectedSlot.slot.slot_id}
                </h3>
                <div class="text-xs space-y-1 text-gray-600">
                  <div>Typ: <strong class="text-gray-800">{selectedSlot.slot.slot_type}</strong></div>
                  <div>Pozice: {Math.round(selectedSlot.slot.rel_x * 990)}x{Math.round(selectedSlot.slot.rel_y * 720)} pt</div>
                  <div>Rozmer: {Math.round(selectedSlot.slot.rel_width * 990)}x{Math.round(selectedSlot.slot.rel_height * 720)} pt</div>
                  {#if selectedSlot.slot.allow_bleed}
                    <div class="text-green-600 font-medium">Bleed povolený</div>
                  {/if}
                </div>

                {#if selectedSlot.image}
                  <div class="mt-3">
                    <div class="text-xs font-medium text-gray-700 mb-1">Prirazena fotka:</div>
                    <img
                      src={api.layoutThumbnailUrl(createdProjectId, selectedSlot.image.filename, 300)}
                      alt={selectedSlot.image.filename}
                      class="w-full rounded-lg border border-gray-200"
                    />
                    <div class="text-[10px] text-gray-500 mt-1">{selectedSlot.image.filename}</div>
                    <div class="text-[10px] text-gray-400">
                      {selectedSlot.image.width}x{selectedSlot.image.height}px &middot;
                      {selectedSlot.image.orientation} &middot;
                      {selectedSlot.image.priority}
                    </div>
                  </div>
                {/if}
              </div>

            {:else if selectedSpreadIdx != null && planDetail.spreads[selectedSpreadIdx]}
              <!-- Detail vybraného spreadu -->
              {@const sel = planDetail.spreads[selectedSpreadIdx]}
              <div class="space-y-3">
                <h3 class="text-sm font-bold text-gray-800">
                  Spread {selectedSpreadIdx + 1}: {sel.spread_type}
                </h3>
                <div class="text-xs space-y-1 text-gray-600">
                  <div>Pattern: <strong class="text-gray-800">{sel.pattern_id}</strong></div>
                  <div>Slotů: <strong>{sel.slots?.length || 0}</strong></div>
                  <div>Fotek: <strong>{sel.assigned_images?.length || 0}</strong></div>
                  {#if sel.notes}
                    <div class="text-gray-500 italic">{sel.notes}</div>
                  {/if}
                </div>

                <!-- Fotky spreadu — draggable -->
                {#if sel.assigned_images?.length > 0}
                  <div class="mt-3">
                    <div class="text-xs font-medium text-gray-700 mb-2">Fotky ve spreadu:</div>
                    <div class="grid grid-cols-2 gap-2">
                      {#each sel.assigned_images as img}
                        <!-- svelte-ignore a11y_no_static_element_interactions -->
                        <div
                          class="relative cursor-grab active:cursor-grabbing rounded-lg overflow-hidden border border-gray-200 hover:border-indigo-400 transition-colors"
                          draggable="true"
                          ondragstart={() => handleImageDragStart(img.filename)}
                          ondragend={handleImageDragEnd}
                        >
                          <img
                            src={api.layoutThumbnailUrl(createdProjectId, img.filename, 200)}
                            alt={img.filename}
                            class="w-full h-16 object-cover"
                          />
                          <div class="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[9px] px-1 py-0.5 truncate">
                            {img.filename}
                          </div>
                          {#if img.priority === 'hero'}
                            <span class="absolute top-0.5 right-0.5 bg-yellow-400 text-yellow-900 text-[8px] font-bold px-1 rounded">H</span>
                          {/if}
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Text sections -->
                {#if sel.assigned_text_sections?.length > 0}
                  <div class="mt-3">
                    <div class="text-xs font-medium text-gray-700 mb-1">Text sekce:</div>
                    <div class="flex flex-wrap gap-1">
                      {#each sel.assigned_text_sections as ts}
                        <span class="bg-blue-50 text-blue-700 text-[10px] px-1.5 py-0.5 rounded">{ts}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>

            {:else}
              <div class="text-center py-10 text-gray-400 text-xs">
                <p>Vyber spread pro zobrazeni detailu</p>
                <p class="mt-2 text-gray-300">Sipkami naviguj, kliknutim vyber slot</p>
              </div>
            {/if}
          </div>
        </div>

      {:else if planResult}
        <!-- Fallback: jednoduchá miniatura (když plan-detail selže) -->
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {#each planResult.spreads || [] as spread, idx}
            <div class="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div class="text-xs font-bold text-gray-700 mb-1">Spread {idx + 1}</div>
              <div class="text-xs text-gray-500 mb-2">{spread.spread_type || spread.pattern_id || '?'}</div>
              <div class="relative bg-white border border-gray-300 rounded" style="aspect-ratio: 990/720;">
                {#each spread.slots || [] as slot, si}
                  {@const l = slot.rel_x != null ? (slot.rel_x * 100) : (si * 25)}
                  {@const t = slot.rel_y != null ? (slot.rel_y * 100) : 10}
                  {@const w = slot.rel_width != null ? (slot.rel_width * 100) : 20}
                  {@const h = slot.rel_height != null ? (slot.rel_height * 100) : 30}
                  <div
                    class="absolute rounded-sm text-[8px] flex items-center justify-center
                           {slot.slot_type?.includes('image')
                             ? 'bg-green-200 border border-green-400 text-green-700'
                             : 'bg-blue-200 border border-blue-400 text-blue-700'}"
                    style="left:{l}%; top:{t}%; width:{w}%; height:{h}%;"
                  >
                    {slot.slot_type?.[0]?.toUpperCase() || '?'}
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
          class="px-4 py-2 text-gray-500 hover:text-gray-700 text-sm border border-gray-200 rounded-lg"
          onclick={() => { step = 4; planResult = null; planDetail = null; }}
        >
          Preplanovot
        </button>
        <button
          class="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
          disabled={!(planResult || planDetail || multiPlanResult) || generating || multiGenerating}
          onclick={() => { step = 6; multiArticleMode ? runMultiGenerate() : runGenerate(); }}
        >
          Generovat IDML &rarr;
        </button>
      </div>
    </div>

  <!-- STEP 6: Generovani -->
  {:else if step === 6}
    <div class="bg-white rounded-xl border border-gray-200 p-6">
      <h2 class="text-lg font-bold text-gray-900 mb-4">
        {multiArticleMode ? 'Multi-article IDML' : batchMode ? 'Batch generovani IDML' : 'Generovani IDML'}
      </h2>

      {#if generating || batchGenerating || multiGenerating}
        <div class="text-center py-10">
          <div class="animate-spin inline-block w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full mb-4"></div>
          <p class="text-indigo-700 font-medium">{multiArticleMode ? multiGenerateMessage : generateMessage}</p>
          {#if batchProgress && batchProgress.total > 0}
            <div class="mt-3 w-64 mx-auto bg-gray-200 rounded-full h-2">
              <div class="bg-purple-600 h-2 rounded-full transition-all"
                   style="width: {Math.round((batchProgress.completed || 0) / batchProgress.total * 100)}%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-1">{batchProgress.completed || 0} / {batchProgress.total} variant</p>
          {/if}
        </div>

      {:else if batchResults}
        <!-- Batch výsledky -->
        <div class="text-center py-6">
          <div class="text-4xl mb-3">&#x2705;</div>
          <p class="text-lg font-bold text-gray-900 mb-4">
            {batchResults.variants?.length || 0} variant vygenerovano!
          </p>
          <div class="flex flex-wrap gap-3 justify-center">
            {#each batchResults.variants || [] as v}
              <button
                class="px-4 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                onclick={() => downloadBatchVariant(v.variant)}
              >
                Varianta {v.variant} ({v.size_kb} KB)
              </button>
            {/each}
          </div>
        </div>

      {:else if multiGenerateResult}
        <div class="text-center py-8">
          <div class="text-4xl mb-3">&#x2705;</div>
          <p class="text-lg font-bold text-gray-900 mb-2">Multi-article IDML vygenerovan!</p>
          <p class="text-sm text-gray-500 mb-2">
            {multiGenerateResult.article_count} clanku &middot; {multiGenerateResult.total_pages} stran &middot; {multiGenerateResult.size_kb || '?'} KB
          </p>
          <button
            class="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors text-sm"
            onclick={downloadIdml}
          >
            Stahnout IDML
          </button>
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
        <button class="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm" onclick={() => { step = 5; loadPlanDetail(); }}>
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
