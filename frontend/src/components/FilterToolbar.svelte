<script>
  let {
    search = $bindable(''),
    filterLayer = $bindable(''),
    filterCategory = $bindable(''),
    filterStatus = $bindable(''),
    layers = [],
    categories = [],
    statuses = [],
  } = $props();

  const categoryLabels = {
    heading: 'Nadpis', subtitle: 'Podnadpis', lead: 'Perex',
    body: 'Text', bullet: 'Odrazka', caption: 'Popisek', separator: 'Separator',
    oceans_seas: 'Oceany/more', continents: 'Kontinenty', countries_full: 'Zeme',
    countries_abbrev: 'Zeme (zkr.)', regions: 'Regiony', cities: 'Mesta',
    water_bodies: 'Vodni plochy', landforms: 'Terenn. utvary', places: 'Mista',
    settlements: 'Sidla', title: 'Titulek', info_boxes: 'Info boxy',
    labels: 'Stitky', annotations: 'Anotace', main_text: 'Hlavni text',
    legend: 'Legenda', scale: 'Meritko', timeline: 'Casova osa',
    credits: 'Kredity', periods: 'Obdobi', events: 'Udalosti', dates: 'Data',
  };
</script>

<div class="flex flex-wrap items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs">
  <input
    type="text"
    placeholder="Hledat text..."
    bind:value={search}
    class="border border-gray-200 rounded px-2 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-blue-400"
  />

  {#if layers.length > 0}
    <select bind:value={filterLayer} class="border border-gray-200 rounded px-1.5 py-1 bg-white">
      <option value="">Vsechny vrstvy</option>
      {#each layers as l}
        <option value={l}>{l}</option>
      {/each}
    </select>
  {/if}

  {#if categories.length > 0}
    <select bind:value={filterCategory} class="border border-gray-200 rounded px-1.5 py-1 bg-white">
      <option value="">Vsechny kategorie</option>
      {#each categories as c}
        <option value={c}>{categoryLabels[c] || c}</option>
      {/each}
    </select>
  {/if}

  <select bind:value={filterStatus} class="border border-gray-200 rounded px-1.5 py-1 bg-white">
    <option value="">Vsechny statusy</option>
    <option value="__none__">Bez statusu</option>
    {#each statuses as s}
      <option value={s}>{s}</option>
    {/each}
  </select>
</div>
