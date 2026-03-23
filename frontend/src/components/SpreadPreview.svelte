<script>
  import { api } from '../lib/api.js';

  /**
   * SVG miniatura jednoho spreadu s rámci a fotkami.
   * Props:
   *   spread — spread objekt z plan-detail API (slots, assigned_images, pattern_id...)
   *   projectId — ID projektu (pro thumbnail URL)
   *   width — šířka SVG v px (default 400)
   *   selected — je spread vybraný?
   *   onSelect — callback při kliknutí na spread
   *   onSlotClick — callback při kliknutí na slot {spread, slot, image?}
   *   onImageDrop — callback při drop fotky na slot {spread, slotId, image}
   *   draggedImage — právě přetahovaná fotka (filename)
   */
  let {
    spread,
    projectId = '',
    width = 400,
    selected = false,
    onSelect = () => {},
    onSlotClick = () => {},
    onImageDrop = () => {},
    draggedImage = null,
  } = $props();

  // Spread poměr stran: 990×720pt (2 stránky)
  const SPREAD_W = 990;
  const SPREAD_H = 720;
  let height = $derived(Math.round(width * SPREAD_H / SPREAD_W));

  // Mapování slot_type na barvy
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
  };

  function slotColor(slotType) {
    return SLOT_COLORS[slotType] || { fill: '#f3f4f6', stroke: '#9ca3af', label: '?' };
  }

  // Přiřadit fotky k image slotům (v pořadí)
  let imageSlotMap = $derived.by(() => {
    if (!spread?.slots || !spread?.assigned_images) return {};
    const imageSlots = spread.slots.filter(s =>
      s.slot_type === 'hero_image' || s.slot_type === 'body_image'
    );
    const map = {};
    for (let i = 0; i < imageSlots.length && i < spread.assigned_images.length; i++) {
      map[imageSlots[i].slot_id] = spread.assigned_images[i];
    }
    return map;
  });

  let hoveredSlot = $state(null);
  let dropTargetSlot = $state(null);

  function handleSlotClick(slot) {
    const img = imageSlotMap[slot.slot_id];
    onSlotClick({ spread, slot, image: img || null });
  }

  function handleDragOver(e, slot) {
    if (!draggedImage) return;
    if (slot.slot_type !== 'hero_image' && slot.slot_type !== 'body_image') return;
    e.preventDefault();
    dropTargetSlot = slot.slot_id;
  }

  function handleDragLeave() {
    dropTargetSlot = null;
  }

  function handleDrop(e, slot) {
    e.preventDefault();
    dropTargetSlot = null;
    if (!draggedImage) return;
    onImageDrop({ spread, slotId: slot.slot_id, image: draggedImage });
  }

  function isImageSlot(slotType) {
    return slotType === 'hero_image' || slotType === 'body_image';
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class="inline-block cursor-pointer rounded-lg overflow-hidden transition-all
         {selected ? 'ring-2 ring-indigo-500 shadow-lg' : 'ring-1 ring-gray-200 hover:ring-gray-400'}"
  onclick={() => onSelect(spread)}
  role="button"
  tabindex="0"
>
  <svg
    viewBox="0 0 {SPREAD_W} {SPREAD_H}"
    {width}
    {height}
    xmlns="http://www.w3.org/2000/svg"
    class="bg-white"
  >
    <!-- Spread background -->
    <rect x="0" y="0" width={SPREAD_W} height={SPREAD_H} fill="#fafafa" stroke="#e5e7eb" stroke-width="1" />

    <!-- Page divider (hřbet) -->
    <line x1={SPREAD_W/2} y1="0" x2={SPREAD_W/2} y2={SPREAD_H} stroke="#d1d5db" stroke-width="1" stroke-dasharray="4,4" />

    <!-- Sloty -->
    {#each spread?.slots || [] as slot}
      {@const x = slot.rel_x * SPREAD_W}
      {@const y = slot.rel_y * SPREAD_H}
      {@const w = slot.rel_width * SPREAD_W}
      {@const h = slot.rel_height * SPREAD_H}
      {@const colors = slotColor(slot.slot_type)}
      {@const img = imageSlotMap[slot.slot_id]}
      {@const isDropTarget = dropTargetSlot === slot.slot_id}

      <g
        class="slot-group"
        onmouseenter={() => { hoveredSlot = slot.slot_id; }}
        onmouseleave={() => { hoveredSlot = null; }}
        onclick={(e) => { e.stopPropagation(); handleSlotClick(slot); }}
        ondragover={(e) => handleDragOver(e, slot)}
        ondragleave={handleDragLeave}
        ondrop={(e) => handleDrop(e, slot)}
      >
        <!-- Slot background -->
        <rect
          {x} {y} width={w} height={h}
          fill={isDropTarget ? '#fef3c7' : colors.fill}
          stroke={isDropTarget ? '#f59e0b' : (hoveredSlot === slot.slot_id ? '#4f46e5' : colors.stroke)}
          stroke-width={hoveredSlot === slot.slot_id ? 2 : 1}
          rx="2"
          opacity="0.85"
        />

        <!-- Thumbnail fotky v image slotu -->
        {#if img && isImageSlot(slot.slot_type) && projectId}
          <image
            href={api.layoutThumbnailUrl(projectId, img.filename, 300)}
            {x} {y} width={w} height={h}
            preserveAspectRatio="xMidYMid slice"
            clip-path="inset(0)"
            opacity="0.9"
          />
          <!-- Poloprůhledný overlay pro čitelnost labelu -->
          <rect {x} y={y + h - 20} width={w} height="20" fill="rgba(0,0,0,0.5)" />
          <text
            x={x + 4} y={y + h - 6}
            font-size="11" fill="white" font-family="system-ui"
          >
            {img.filename.length > 20 ? img.filename.slice(0, 18) + '…' : img.filename}
          </text>
        {:else}
          <!-- Label slotu -->
          <text
            x={x + w/2} y={y + h/2 + 4}
            text-anchor="middle" dominant-baseline="middle"
            font-size={w > 80 && h > 30 ? 13 : 9}
            fill={colors.stroke}
            font-family="system-ui"
            font-weight="600"
          >
            {colors.label}
          </text>
        {/if}
      </g>
    {/each}

    <!-- Spread type label -->
    <text x="6" y="16" font-size="11" fill="#6b7280" font-family="system-ui" font-weight="500">
      {spread?.spread_type || ''}
    </text>
    <text x={SPREAD_W - 6} y="16" text-anchor="end" font-size="10" fill="#9ca3af" font-family="system-ui">
      {spread?.pattern_id || ''}
    </text>
  </svg>
</div>
