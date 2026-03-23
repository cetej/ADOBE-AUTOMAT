<script>
  import { api } from '../lib/api.js';
  import { navigate } from '../stores/router.js';
  import { notify } from '../stores/notifications.js';

  // --- State ---
  let patterns = $state([]);
  let selectedPatternId = $state(null);
  let loading = $state(true);
  let saving = $state(false);

  // Editor state
  let editorMode = $state('select'); // select, draw
  let slots = $state([]);
  let patternMeta = $state({
    pattern_id: '',
    pattern_name: '',
    spread_type: 'body_mixed',
    description: '',
    min_images: 0,
    max_images: 10,
    min_text_chars: 0,
    preferred_for: [],
  });

  // Drawing state
  let drawStart = $state(null);
  let drawCurrent = $state(null);
  let isDrawing = $state(false);

  // Drag/Resize state
  let dragState = $state(null); // { slotIdx, mode: 'move'|'resize-se'|..., startX, startY, origSlot }
  let selectedSlotIdx = $state(null);

  // Validation
  let validation = $state(null);

  // SVG dimensions
  const SPREAD_W = 990;
  const SPREAD_H = 720;
  const SVG_W = 760;
  let SVG_H = $derived(Math.round(SVG_W * SPREAD_H / SPREAD_W));
  let scale = $derived(SVG_W / SPREAD_W);

  // Guides
  const LEFT_MARGIN = 57 / 990;
  const RIGHT_MARGIN = 48 / 990;
  const TOP_MARGIN = 75 / 720;
  const BOTTOM_MARGIN = 84 / 720;
  const PAGE_MID = 0.5;
  let showGrid = $state(true);

  // Slot type colors (consistent with SpreadPreview)
  const SLOT_COLORS = {
    hero_image: { fill: '#86efac', stroke: '#16a34a', label: 'Hero' },
    body_image: { fill: '#bbf7d0', stroke: '#22c55e', label: 'Foto' },
    body_text:  { fill: '#bfdbfe', stroke: '#3b82f6', label: 'Text' },
    headline:   { fill: '#c4b5fd', stroke: '#7c3aed', label: 'H' },
    deck:       { fill: '#ddd6fe', stroke: '#8b5cf6', label: 'D' },
    byline:     { fill: '#e9d5ff', stroke: '#a855f7', label: 'By' },
    caption:    { fill: '#a5f3fc', stroke: '#06b6d4', label: 'Cap' },
    pull_quote: { fill: '#fde68a', stroke: '#f59e0b', label: 'PQ' },
    folio:      { fill: '#e5e7eb', stroke: '#6b7280', label: 'F' },
    credit:     { fill: '#e5e7eb', stroke: '#9ca3af', label: 'Cr' },
    sidebar:    { fill: '#fbcfe8', stroke: '#ec4899', label: 'SB' },
    map_art:    { fill: '#d1fae5', stroke: '#059669', label: 'Map' },
    logo:       { fill: '#fef3c7', stroke: '#d97706', label: 'Logo' },
    cover_line: { fill: '#fed7aa', stroke: '#ea580c', label: 'CL' },
    unknown:    { fill: '#f3f4f6', stroke: '#9ca3af', label: '?' },
  };

  const FRAME_TYPES = [
    'hero_image', 'body_image', 'body_text', 'headline', 'deck',
    'byline', 'caption', 'pull_quote', 'folio', 'credit',
    'sidebar', 'map_art', 'logo', 'cover_line',
  ];

  const SPREAD_TYPES = [
    'opening', 'body_mixed', 'body_text', 'photo_grid', 'photo_dominant',
    'big_picture', 'closing', 'cover', 'toc', 'frontmatter', 'map_infographic',
  ];

  // --- Presets ---
  const PRESETS = [
    {
      id: 'two-column', name: '2 sloupce + fotka',
      slots: [
        { slot_id: 'body_text', slot_type: 'body_text', rel_x: 0.058, rel_y: 0.104, rel_width: 0.42, rel_height: 0.78, required: true },
        { slot_id: 'image_1', slot_type: 'body_image', rel_x: 0.52, rel_y: 0.104, rel_width: 0.43, rel_height: 0.65, required: true },
        { slot_id: 'caption_1', slot_type: 'caption', rel_x: 0.52, rel_y: 0.78, rel_width: 0.30, rel_height: 0.05, required: false },
      ],
    },
    {
      id: 'fullbleed-caption', name: 'Full-bleed + caption',
      slots: [
        { slot_id: 'hero', slot_type: 'hero_image', rel_x: 0.0, rel_y: 0.0, rel_width: 1.0, rel_height: 1.0, required: true, allow_bleed: true },
        { slot_id: 'caption', slot_type: 'caption', rel_x: 0.55, rel_y: 0.92, rel_width: 0.35, rel_height: 0.05, required: false },
      ],
    },
    {
      id: 'grid-3x2', name: 'Grid 3×2',
      slots: [
        { slot_id: 'image_1', slot_type: 'body_image', rel_x: 0.058, rel_y: 0.104, rel_width: 0.28, rel_height: 0.35, required: true },
        { slot_id: 'image_2', slot_type: 'body_image', rel_x: 0.358, rel_y: 0.104, rel_width: 0.28, rel_height: 0.35, required: true },
        { slot_id: 'image_3', slot_type: 'body_image', rel_x: 0.658, rel_y: 0.104, rel_width: 0.28, rel_height: 0.35, required: true },
        { slot_id: 'image_4', slot_type: 'body_image', rel_x: 0.058, rel_y: 0.50, rel_width: 0.28, rel_height: 0.35, required: false },
        { slot_id: 'image_5', slot_type: 'body_image', rel_x: 0.358, rel_y: 0.50, rel_width: 0.28, rel_height: 0.35, required: false },
        { slot_id: 'image_6', slot_type: 'body_image', rel_x: 0.658, rel_y: 0.50, rel_width: 0.28, rel_height: 0.35, required: false },
      ],
    },
    {
      id: 'text-heavy', name: 'Text-heavy 3 sloupce',
      slots: [
        { slot_id: 'body_text', slot_type: 'body_text', rel_x: 0.058, rel_y: 0.104, rel_width: 0.884, rel_height: 0.78, required: true },
        { slot_id: 'image_1', slot_type: 'body_image', rel_x: 0.68, rel_y: 0.104, rel_width: 0.26, rel_height: 0.30, required: false },
      ],
    },
  ];

  // --- Init ---
  loadPatterns();

  async function loadPatterns() {
    loading = true;
    try {
      const res = await api.layoutPatternsDetail();
      patterns = res.patterns || [];
    } catch (e) {
      notify('Chyba načítání patterns: ' + e.message, 'error');
    }
    loading = false;
  }

  function selectPattern(p) {
    selectedPatternId = p.id;
    patternMeta = {
      pattern_id: p.id,
      pattern_name: p.name,
      spread_type: p.type,
      description: p.description || '',
      min_images: p.min_images || 0,
      max_images: p.max_images || 10,
      min_text_chars: p.min_text_chars || 0,
      preferred_for: p.preferred_for || [],
    };
    slots = (p.slots || []).map(s => ({ ...s }));
    validation = null;
    selectedSlotIdx = null;
  }

  function newPattern() {
    selectedPatternId = null;
    patternMeta = {
      pattern_id: '',
      pattern_name: '',
      spread_type: 'body_mixed',
      description: '',
      min_images: 0,
      max_images: 10,
      min_text_chars: 0,
      preferred_for: [],
    };
    slots = [];
    validation = null;
    selectedSlotIdx = null;
  }

  function applyPreset(preset) {
    slots = preset.slots.map(s => ({ ...s }));
    if (!patternMeta.pattern_name) {
      patternMeta.pattern_name = 'Custom — ' + preset.name;
    }
    selectedSlotIdx = null;
    validation = null;
  }

  // --- SVG coordinate conversion ---
  let svgEl = $state(null);

  function svgToRel(clientX, clientY) {
    if (!svgEl) return { x: 0, y: 0 };
    const rect = svgEl.getBoundingClientRect();
    const x = (clientX - rect.left) / rect.width;
    const y = (clientY - rect.top) / rect.height;
    return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
  }

  // Snap to guides (5pt threshold = 0.005 relative)
  function snap(val, guides, threshold = 0.008) {
    for (const g of guides) {
      if (Math.abs(val - g) < threshold) return g;
    }
    return val;
  }

  const X_GUIDES = [0, LEFT_MARGIN, PAGE_MID, 1 - RIGHT_MARGIN, 1];
  const Y_GUIDES = [0, TOP_MARGIN, 1 - BOTTOM_MARGIN, 1];

  function snapX(val) { return snap(val, X_GUIDES); }
  function snapY(val) { return snap(val, Y_GUIDES); }

  // --- Drawing new slots ---
  function handleSvgMouseDown(e) {
    if (editorMode !== 'draw') return;
    const pos = svgToRel(e.clientX, e.clientY);
    drawStart = pos;
    drawCurrent = pos;
    isDrawing = true;
  }

  function handleSvgMouseMove(e) {
    if (!isDrawing) return;
    drawCurrent = svgToRel(e.clientX, e.clientY);
  }

  function handleSvgMouseUp(e) {
    if (!isDrawing || !drawStart) { isDrawing = false; return; }
    const end = svgToRel(e.clientX, e.clientY);

    const x1 = snapX(Math.min(drawStart.x, end.x));
    const y1 = snapY(Math.min(drawStart.y, end.y));
    const x2 = snapX(Math.max(drawStart.x, end.x));
    const y2 = snapY(Math.max(drawStart.y, end.y));
    const w = x2 - x1;
    const h = y2 - y1;

    isDrawing = false;
    drawStart = null;
    drawCurrent = null;

    if (w < 0.03 || h < 0.03) return; // příliš malý

    const idx = slots.length + 1;
    const newSlot = {
      slot_id: `slot_${idx}`,
      slot_type: 'body_image',
      rel_x: round4(x1),
      rel_y: round4(y1),
      rel_width: round4(w),
      rel_height: round4(h),
      required: false,
      allow_bleed: false,
      default_style: null,
    };
    slots = [...slots, newSlot];
    selectedSlotIdx = slots.length - 1;
    editorMode = 'select';
    validation = null;
  }

  function round4(n) { return Math.round(n * 10000) / 10000; }

  // --- Drag / Resize slots ---
  function handleSlotMouseDown(e, idx) {
    if (editorMode !== 'select') return;
    e.stopPropagation();
    selectedSlotIdx = idx;

    const pos = svgToRel(e.clientX, e.clientY);
    const slot = slots[idx];

    // Detect handle: if click is near bottom-right corner → resize
    const cornerThreshold = 0.025;
    const isNearRight = Math.abs(pos.x - (slot.rel_x + slot.rel_width)) < cornerThreshold;
    const isNearBottom = Math.abs(pos.y - (slot.rel_y + slot.rel_height)) < cornerThreshold;

    dragState = {
      slotIdx: idx,
      mode: (isNearRight && isNearBottom) ? 'resize' : 'move',
      startX: pos.x,
      startY: pos.y,
      origSlot: { ...slot },
    };

    window.addEventListener('mousemove', handleDragMove);
    window.addEventListener('mouseup', handleDragEnd);
  }

  function handleDragMove(e) {
    if (!dragState) return;
    const pos = svgToRel(e.clientX, e.clientY);
    const dx = pos.x - dragState.startX;
    const dy = pos.y - dragState.startY;
    const orig = dragState.origSlot;
    const idx = dragState.slotIdx;

    if (dragState.mode === 'move') {
      let newX = snapX(orig.rel_x + dx);
      let newY = snapY(orig.rel_y + dy);
      // Clamp
      newX = Math.max(0, Math.min(1 - orig.rel_width, newX));
      newY = Math.max(0, Math.min(1 - orig.rel_height, newY));
      slots[idx] = { ...slots[idx], rel_x: round4(newX), rel_y: round4(newY) };
    } else {
      // Resize
      let newW = snapX(orig.rel_x + orig.rel_width + dx) - orig.rel_x;
      let newH = snapY(orig.rel_y + orig.rel_height + dy) - orig.rel_y;
      newW = Math.max(0.05, Math.min(1 - orig.rel_x, newW));
      newH = Math.max(0.05, Math.min(1 - orig.rel_y, newH));
      slots[idx] = { ...slots[idx], rel_width: round4(newW), rel_height: round4(newH) };
    }
    slots = [...slots]; // trigger reactivity
  }

  function handleDragEnd() {
    dragState = null;
    window.removeEventListener('mousemove', handleDragMove);
    window.removeEventListener('mouseup', handleDragEnd);
    validation = null;
  }

  // --- Slot operations ---
  function deleteSlot(idx) {
    slots = slots.filter((_, i) => i !== idx);
    if (selectedSlotIdx === idx) selectedSlotIdx = null;
    else if (selectedSlotIdx > idx) selectedSlotIdx--;
    validation = null;
  }

  function duplicateSlot(idx) {
    const src = slots[idx];
    const newSlot = {
      ...src,
      slot_id: src.slot_id + '_copy',
      rel_x: round4(Math.min(src.rel_x + 0.05, 0.95)),
      rel_y: round4(Math.min(src.rel_y + 0.05, 0.95)),
    };
    slots = [...slots, newSlot];
    selectedSlotIdx = slots.length - 1;
    validation = null;
  }

  // --- Validate ---
  async function validatePattern() {
    const data = buildPatternData();
    if (!data) return;
    try {
      validation = await api.layoutValidatePattern(data);
    } catch (e) {
      validation = { valid: false, errors: [e.message], warnings: [] };
    }
  }

  // --- Save ---
  function buildPatternData() {
    if (!patternMeta.pattern_id) {
      notify('Zadejte pattern ID', 'error');
      return null;
    }
    return {
      ...patternMeta,
      slots: slots.map(s => ({
        slot_id: s.slot_id,
        slot_type: s.slot_type,
        rel_x: s.rel_x,
        rel_y: s.rel_y,
        rel_width: s.rel_width,
        rel_height: s.rel_height,
        required: s.required ?? false,
        allow_bleed: s.allow_bleed ?? false,
        default_style: s.default_style || null,
      })),
    };
  }

  async function savePattern() {
    const data = buildPatternData();
    if (!data) return;
    saving = true;
    try {
      // Pokud existuje v patterns a je custom → update, jinak create
      const existing = patterns.find(p => p.id === data.pattern_id);
      if (existing && !existing.is_builtin) {
        await api.layoutUpdatePattern(data.pattern_id, data);
        notify(`Pattern "${data.pattern_name}" aktualizován`, 'success');
      } else {
        await api.layoutCreatePattern(data);
        notify(`Pattern "${data.pattern_name}" vytvořen`, 'success');
      }
      await loadPatterns();
    } catch (e) {
      const msg = typeof e.message === 'string' ? e.message : JSON.stringify(e.message);
      notify('Chyba ukládání: ' + msg, 'error');
    }
    saving = false;
  }

  async function deletePattern(patternId) {
    if (!confirm(`Smazat pattern "${patternId}"?`)) return;
    try {
      await api.layoutDeletePattern(patternId);
      notify('Pattern smazán', 'success');
      if (selectedPatternId === patternId) newPattern();
      await loadPatterns();
    } catch (e) {
      notify('Chyba mazání: ' + e.message, 'error');
    }
  }

  // Drawing preview rect
  let drawRect = $derived.by(() => {
    if (!isDrawing || !drawStart || !drawCurrent) return null;
    return {
      x: Math.min(drawStart.x, drawCurrent.x) * SPREAD_W,
      y: Math.min(drawStart.y, drawCurrent.y) * SPREAD_H,
      w: Math.abs(drawCurrent.x - drawStart.x) * SPREAD_W,
      h: Math.abs(drawCurrent.y - drawStart.y) * SPREAD_H,
    };
  });

  function slotColor(type) {
    return SLOT_COLORS[type] || SLOT_COLORS.unknown;
  }

  // Column grid (12 columns)
  const COL_COUNT = 12;
  const GUTTER = 24 / 990; // 24pt gutter
  let columnLines = $derived.by(() => {
    const lines = [];
    const contentLeft = LEFT_MARGIN;
    const contentRight = 1 - RIGHT_MARGIN;
    // Left page (0 to 0.5)
    const leftPageW = PAGE_MID - contentLeft;
    const colW = (leftPageW - GUTTER * 5) / 6;
    for (let i = 0; i <= 6; i++) {
      lines.push(contentLeft + i * (colW + GUTTER));
    }
    // Right page (0.5 to 1)
    const rightStart = PAGE_MID;
    const rightPageW = contentRight - rightStart;
    const colW2 = (rightPageW - GUTTER * 5) / 6;
    for (let i = 0; i <= 6; i++) {
      lines.push(rightStart + i * (colW2 + GUTTER));
    }
    return lines;
  });
</script>

<div class="flex gap-4 h-[calc(100vh-8rem)]">
  <!-- Left sidebar: Pattern list -->
  <div class="w-64 flex-shrink-0 bg-white rounded-lg border border-gray-200 overflow-y-auto">
    <div class="p-3 border-b border-gray-100">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold text-gray-700">Patterns</h3>
        <button
          class="text-xs px-2 py-1 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100"
          onclick={newPattern}
        >
          + Nový
        </button>
      </div>
      <button
        class="w-full text-xs text-gray-500 hover:text-gray-700 text-left"
        onclick={() => navigate('layout-wizard')}
      >
        ← Zpět do wizardu
      </button>
    </div>

    {#if loading}
      <div class="p-4 text-center text-gray-400 text-sm">Načítám...</div>
    {:else}
      {#each patterns as p}
        <button
          class="w-full text-left px-3 py-2 text-sm border-b border-gray-50 hover:bg-gray-50 transition
                 {selectedPatternId === p.id ? 'bg-indigo-50 border-l-2 border-l-indigo-500' : ''}"
          onclick={() => selectPattern(p)}
        >
          <div class="font-medium text-gray-800 truncate">{p.name}</div>
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-xs text-gray-400">{p.type}</span>
            <span class="text-xs text-gray-300">{p.slots_count || p.slots?.length || 0} slotů</span>
            {#if !p.is_builtin}
              <span class="text-xs px-1 py-0.5 rounded bg-amber-50 text-amber-600">custom</span>
            {/if}
          </div>
        </button>
      {/each}
    {/if}
  </div>

  <!-- Main: SVG editor -->
  <div class="flex-1 flex flex-col bg-white rounded-lg border border-gray-200 overflow-hidden">
    <!-- Toolbar -->
    <div class="px-4 py-2 border-b border-gray-200 flex items-center gap-3 flex-wrap">
      <div class="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
        <button
          class="px-3 py-1 text-xs rounded-md transition {editorMode === 'select' ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'}"
          onclick={() => { editorMode = 'select'; }}
        >
          Vybrat
        </button>
        <button
          class="px-3 py-1 text-xs rounded-md transition {editorMode === 'draw' ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'}"
          onclick={() => { editorMode = 'draw'; selectedSlotIdx = null; }}
        >
          Kreslit
        </button>
      </div>

      <label class="flex items-center gap-1 text-xs text-gray-500">
        <input type="checkbox" bind:checked={showGrid} class="rounded" />
        Grid
      </label>

      <div class="flex-1"></div>

      <!-- Preset buttons -->
      <span class="text-xs text-gray-400">Presety:</span>
      {#each PRESETS as preset}
        <button
          class="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
          onclick={() => applyPreset(preset)}
        >
          {preset.name}
        </button>
      {/each}
    </div>

    <!-- SVG Canvas -->
    <div class="flex-1 flex items-center justify-center p-4 bg-gray-50 overflow-auto">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <svg
        bind:this={svgEl}
        viewBox="0 0 {SPREAD_W} {SPREAD_H}"
        width={SVG_W}
        height={SVG_H}
        xmlns="http://www.w3.org/2000/svg"
        class="bg-white shadow-lg rounded cursor-{editorMode === 'draw' ? 'crosshair' : 'default'}"
        onmousedown={handleSvgMouseDown}
        onmousemove={handleSvgMouseMove}
        onmouseup={handleSvgMouseUp}
      >
        <!-- Background -->
        <rect x="0" y="0" width={SPREAD_W} height={SPREAD_H} fill="white" stroke="#d1d5db" stroke-width="1" />

        <!-- Margin guides -->
        <rect
          x={LEFT_MARGIN * SPREAD_W} y={TOP_MARGIN * SPREAD_H}
          width={(1 - LEFT_MARGIN - RIGHT_MARGIN) * SPREAD_W}
          height={(1 - TOP_MARGIN - BOTTOM_MARGIN) * SPREAD_H}
          fill="none" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="4,4"
        />

        <!-- Page divider -->
        <line
          x1={PAGE_MID * SPREAD_W} y1="0"
          x2={PAGE_MID * SPREAD_W} y2={SPREAD_H}
          stroke="#d1d5db" stroke-width="1" stroke-dasharray="6,3"
        />

        <!-- Column grid -->
        {#if showGrid}
          {#each columnLines as cx}
            <line
              x1={cx * SPREAD_W} y1={TOP_MARGIN * SPREAD_H}
              x2={cx * SPREAD_W} y2={(1 - BOTTOM_MARGIN) * SPREAD_H}
              stroke="#f3f4f6" stroke-width="0.5"
            />
          {/each}
        {/if}

        <!-- Slots -->
        {#each slots as slot, idx}
          {@const x = slot.rel_x * SPREAD_W}
          {@const y = slot.rel_y * SPREAD_H}
          {@const w = slot.rel_width * SPREAD_W}
          {@const h = slot.rel_height * SPREAD_H}
          {@const colors = slotColor(slot.slot_type)}
          {@const isSelected = selectedSlotIdx === idx}
          {@const hasOverlap = validation && validation.errors?.some(e => e.includes(slot.slot_id) && e.includes('překrývají'))}

          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <g
            onmousedown={(e) => handleSlotMouseDown(e, idx)}
            class="cursor-{editorMode === 'select' ? 'move' : 'default'}"
          >
            <!-- Slot rect -->
            <rect
              {x} {y} width={w} height={h}
              fill={hasOverlap ? '#fecaca' : colors.fill}
              stroke={isSelected ? '#4f46e5' : (hasOverlap ? '#ef4444' : colors.stroke)}
              stroke-width={isSelected ? 2.5 : 1}
              rx="2"
              opacity="0.85"
            />

            <!-- Label -->
            <text
              x={x + w / 2} y={y + h / 2 + 4}
              text-anchor="middle" dominant-baseline="middle"
              font-size={w > 80 && h > 30 ? 13 : 9}
              fill={colors.stroke} font-family="system-ui" font-weight="600"
            >
              {slot.slot_id}
            </text>

            <!-- Type badge -->
            {#if w > 60 && h > 40}
              <text
                x={x + 4} y={y + 14}
                font-size="9" fill={colors.stroke} font-family="system-ui" opacity="0.7"
              >
                {colors.label}
              </text>
            {/if}

            <!-- Resize handle (bottom-right) -->
            {#if isSelected && editorMode === 'select'}
              <rect
                x={x + w - 8} y={y + h - 8} width="8" height="8"
                fill="#4f46e5" rx="1" class="cursor-se-resize"
              />
            {/if}
          </g>
        {/each}

        <!-- Drawing preview -->
        {#if drawRect}
          <rect
            x={drawRect.x} y={drawRect.y}
            width={drawRect.w} height={drawRect.h}
            fill="rgba(99, 102, 241, 0.15)"
            stroke="#6366f1" stroke-width="1.5" stroke-dasharray="4,4"
            rx="2"
          />
        {/if}

        <!-- Spread labels -->
        <text x="6" y="16" font-size="10" fill="#9ca3af" font-family="system-ui">Levá stránka</text>
        <text x={SPREAD_W / 2 + 6} y="16" font-size="10" fill="#9ca3af" font-family="system-ui">Pravá stránka</text>
      </svg>
    </div>
  </div>

  <!-- Right sidebar: Properties -->
  <div class="w-72 flex-shrink-0 bg-white rounded-lg border border-gray-200 overflow-y-auto">
    <div class="p-3 border-b border-gray-100">
      <h3 class="text-sm font-semibold text-gray-700">Vlastnosti patternu</h3>
    </div>
    <div class="p-3 space-y-3">
      <div>
        <label class="block text-xs text-gray-500 mb-1">ID (kebab-case)</label>
        <input
          type="text" bind:value={patternMeta.pattern_id}
          class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
          placeholder="my-custom-pattern"
          disabled={patterns.find(p => p.id === patternMeta.pattern_id)?.is_builtin}
        />
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">Název</label>
        <input type="text" bind:value={patternMeta.pattern_name}
               class="w-full text-sm border border-gray-200 rounded px-2 py-1.5" />
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">Typ spreadu</label>
        <select bind:value={patternMeta.spread_type}
                class="w-full text-sm border border-gray-200 rounded px-2 py-1.5">
          {#each SPREAD_TYPES as t}
            <option value={t}>{t}</option>
          {/each}
        </select>
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">Popis</label>
        <textarea bind:value={patternMeta.description}
                  class="w-full text-sm border border-gray-200 rounded px-2 py-1.5" rows="2"></textarea>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block text-xs text-gray-500 mb-1">Min images</label>
          <input type="number" bind:value={patternMeta.min_images}
                 class="w-full text-sm border border-gray-200 rounded px-2 py-1.5" min="0" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Max images</label>
          <input type="number" bind:value={patternMeta.max_images}
                 class="w-full text-sm border border-gray-200 rounded px-2 py-1.5" min="0" />
        </div>
      </div>
    </div>

    <!-- Selected Slot Properties -->
    {#if selectedSlotIdx !== null && slots[selectedSlotIdx]}
      {@const slot = slots[selectedSlotIdx]}
      <div class="border-t border-gray-200 p-3 space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-semibold text-gray-600 uppercase">Slot: {slot.slot_id}</h4>
          <div class="flex gap-1">
            <button class="text-xs text-indigo-500 hover:text-indigo-700" onclick={() => duplicateSlot(selectedSlotIdx)}>Duplikovat</button>
            <button class="text-xs text-red-500 hover:text-red-700" onclick={() => deleteSlot(selectedSlotIdx)}>Smazat</button>
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Slot ID</label>
          <input type="text" bind:value={slots[selectedSlotIdx].slot_id}
                 class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                 onchange={() => { slots = [...slots]; }} />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Typ</label>
          <select bind:value={slots[selectedSlotIdx].slot_type}
                  class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                  onchange={() => { slots = [...slots]; }}>
            {#each FRAME_TYPES as ft}
              {@const c = slotColor(ft)}
              <option value={ft}>{c.label} — {ft}</option>
            {/each}
          </select>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs text-gray-500 mb-1">X</label>
            <input type="number" step="0.001" bind:value={slots[selectedSlotIdx].rel_x}
                   class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                   onchange={() => { slots = [...slots]; }} />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Y</label>
            <input type="number" step="0.001" bind:value={slots[selectedSlotIdx].rel_y}
                   class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                   onchange={() => { slots = [...slots]; }} />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Šířka</label>
            <input type="number" step="0.001" bind:value={slots[selectedSlotIdx].rel_width}
                   class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                   onchange={() => { slots = [...slots]; }} />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Výška</label>
            <input type="number" step="0.001" bind:value={slots[selectedSlotIdx].rel_height}
                   class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                   onchange={() => { slots = [...slots]; }} />
          </div>
        </div>
        <div class="flex items-center gap-4">
          <label class="flex items-center gap-1 text-xs text-gray-600">
            <input type="checkbox" bind:checked={slots[selectedSlotIdx].required}
                   class="rounded" onchange={() => { slots = [...slots]; }} />
            Povinný
          </label>
          <label class="flex items-center gap-1 text-xs text-gray-600">
            <input type="checkbox" bind:checked={slots[selectedSlotIdx].allow_bleed}
                   class="rounded" onchange={() => { slots = [...slots]; }} />
            Bleed
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">InDesign styl</label>
          <input type="text" bind:value={slots[selectedSlotIdx].default_style}
                 class="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
                 placeholder="ALL_Body_Justified"
                 onchange={() => { slots = [...slots]; }} />
        </div>
      </div>
    {:else}
      <div class="border-t border-gray-200 p-3">
        <p class="text-xs text-gray-400 text-center py-4">
          {editorMode === 'draw' ? 'Nakreslete nový slot na plátně' : 'Klikněte na slot pro úpravu'}
        </p>
      </div>
    {/if}

    <!-- Slot list -->
    <div class="border-t border-gray-200 p-3">
      <h4 class="text-xs font-semibold text-gray-600 uppercase mb-2">Sloty ({slots.length})</h4>
      <div class="space-y-1 max-h-40 overflow-y-auto">
        {#each slots as slot, idx}
          {@const colors = slotColor(slot.slot_type)}
          <button
            class="w-full flex items-center gap-2 text-left px-2 py-1 rounded text-xs
                   {selectedSlotIdx === idx ? 'bg-indigo-50' : 'hover:bg-gray-50'}"
            onclick={() => { selectedSlotIdx = idx; }}
          >
            <span class="w-3 h-3 rounded-sm flex-shrink-0" style="background: {colors.fill}; border: 1px solid {colors.stroke}"></span>
            <span class="font-medium text-gray-700 truncate flex-1">{slot.slot_id}</span>
            <span class="text-gray-400">{colors.label}</span>
          </button>
        {/each}
      </div>
    </div>

    <!-- Validation -->
    {#if validation}
      <div class="border-t border-gray-200 p-3">
        <h4 class="text-xs font-semibold uppercase mb-2 {validation.valid ? 'text-green-600' : 'text-red-600'}">
          {validation.valid ? 'Validace OK' : 'Chyby'}
        </h4>
        {#each validation.errors || [] as err}
          <p class="text-xs text-red-600 mb-1">{err}</p>
        {/each}
        {#each validation.warnings || [] as warn}
          <p class="text-xs text-amber-600 mb-1">{warn}</p>
        {/each}
      </div>
    {/if}

    <!-- Actions -->
    <div class="border-t border-gray-200 p-3 space-y-2">
      <button
        class="w-full text-sm px-3 py-2 rounded bg-gray-100 text-gray-700 hover:bg-gray-200"
        onclick={validatePattern}
      >
        Validovat
      </button>
      <button
        class="w-full text-sm px-3 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
        onclick={savePattern}
        disabled={saving || !patternMeta.pattern_id || !patternMeta.pattern_name || slots.length === 0}
      >
        {saving ? 'Ukládám...' : (selectedPatternId && !patterns.find(p => p.id === selectedPatternId)?.is_builtin ? 'Aktualizovat' : 'Uložit jako custom')}
      </button>
    </div>
  </div>
</div>
