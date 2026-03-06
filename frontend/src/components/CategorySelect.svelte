<script>
  let { value = $bindable(null), compact = false, onchange = null, projectType = 'map' } = $props();

  const mapCategories = [
    { group: 'Geografie', items: [
      { value: 'oceans_seas', label: 'Oceany/more' },
      { value: 'continents', label: 'Kontinenty' },
      { value: 'countries_full', label: 'Zeme' },
      { value: 'countries_abbrev', label: 'Zeme (zkr.)' },
      { value: 'regions', label: 'Regiony' },
      { value: 'cities', label: 'Mesta' },
      { value: 'water_bodies', label: 'Vodni plochy' },
      { value: 'landforms', label: 'Terenn. utvary' },
      { value: 'places', label: 'Mista' },
      { value: 'settlements', label: 'Sidla' },
    ]},
    { group: 'Obsah', items: [
      { value: 'title', label: 'Titulek' },
      { value: 'info_boxes', label: 'Info boxy' },
      { value: 'labels', label: 'Stitky' },
      { value: 'annotations', label: 'Anotace' },
      { value: 'main_text', label: 'Hlavni text' },
    ]},
    { group: 'Reference', items: [
      { value: 'legend', label: 'Legenda' },
      { value: 'scale', label: 'Meritko' },
      { value: 'timeline', label: 'Casova osa' },
      { value: 'credits', label: 'Kredity' },
    ]},
    { group: 'Historie', items: [
      { value: 'periods', label: 'Obdobi' },
      { value: 'events', label: 'Udalosti' },
      { value: 'dates', label: 'Data' },
    ]},
  ];

  const idmlCategories = [
    { group: 'Typ textu', items: [
      { value: 'heading', label: 'Nadpis' },
      { value: 'subtitle', label: 'Podnadpis' },
      { value: 'lead', label: 'Perex' },
      { value: 'body', label: 'Text' },
      { value: 'bullet', label: 'Odrazka' },
      { value: 'caption', label: 'Popisek' },
      { value: 'separator', label: 'Separator' },
    ]},
  ];

  let categories = $derived(projectType === 'idml' ? idmlCategories : mapCategories);

  function handleChange(e) {
    value = e.target.value || null;
    if (onchange) onchange(e);
  }
</script>

<select
  {value}
  onchange={handleChange}
  class="text-xs border border-gray-200 rounded px-1.5 py-0.5 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400
         {compact ? 'w-24' : 'w-32'}"
>
  <option value="">--</option>
  {#each categories as group}
    <optgroup label={group.group}>
      {#each group.items as item}
        <option value={item.value}>{item.label}</option>
      {/each}
    </optgroup>
  {/each}
</select>
