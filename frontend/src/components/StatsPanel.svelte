<script>
  let { elements = [] } = $props();

  let stats = $derived.by(() => {
    const total = elements.length;
    const translated = elements.filter(e => e.czech).length;
    const byStatus = {};
    const byCategory = {};
    const byLayer = {};

    for (const el of elements) {
      const s = el.status || '(bez statusu)';
      byStatus[s] = (byStatus[s] || 0) + 1;

      if (el.category) {
        byCategory[el.category] = (byCategory[el.category] || 0) + 1;
      }
      if (el.layer_name) {
        byLayer[el.layer_name] = (byLayer[el.layer_name] || 0) + 1;
      }
    }

    return { total, translated, byStatus, byCategory, byLayer };
  });
</script>

<div class="bg-white rounded-xl border border-gray-200 p-4 text-sm space-y-4">
  <h3 class="font-semibold text-gray-700">Statistiky</h3>

  <div class="grid grid-cols-2 gap-2">
    <div class="bg-blue-50 rounded-lg p-2 text-center">
      <div class="text-lg font-bold text-blue-700">{stats.total}</div>
      <div class="text-xs text-blue-500">Celkem</div>
    </div>
    <div class="bg-green-50 rounded-lg p-2 text-center">
      <div class="text-lg font-bold text-green-700">{stats.translated}</div>
      <div class="text-xs text-green-500">Prelozeno</div>
    </div>
  </div>

  {#if stats.total > 0}
    <div class="w-full bg-gray-200 rounded-full h-2">
      <div
        class="bg-green-500 h-2 rounded-full transition-all"
        style="width: {Math.round(stats.translated / stats.total * 100)}%"
      ></div>
    </div>
    <div class="text-xs text-gray-500 text-center">
      {Math.round(stats.translated / stats.total * 100)}% prelozeno
    </div>
  {/if}

  <div>
    <h4 class="text-xs font-medium text-gray-500 uppercase mb-1">Statusy</h4>
    {#each Object.entries(stats.byStatus) as [status, count]}
      <div class="flex justify-between text-xs py-0.5">
        <span class="text-gray-600">{status}</span>
        <span class="font-medium">{count}</span>
      </div>
    {/each}
  </div>

  {#if Object.keys(stats.byCategory).length > 0}
    <div>
      <h4 class="text-xs font-medium text-gray-500 uppercase mb-1">Kategorie</h4>
      {#each Object.entries(stats.byCategory).sort((a, b) => b[1] - a[1]) as [cat, count]}
        <div class="flex justify-between text-xs py-0.5">
          <span class="text-gray-600 truncate mr-2">{cat}</span>
          <span class="font-medium">{count}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if Object.keys(stats.byLayer).length > 0}
    <div>
      <h4 class="text-xs font-medium text-gray-500 uppercase mb-1">Vrstvy</h4>
      {#each Object.entries(stats.byLayer).sort((a, b) => b[1] - a[1]).slice(0, 10) as [layer, count]}
        <div class="flex justify-between text-xs py-0.5">
          <span class="text-gray-600 truncate mr-2">{layer}</span>
          <span class="font-medium">{count}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>
