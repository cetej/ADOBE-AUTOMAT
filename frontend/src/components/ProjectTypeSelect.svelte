<script>
  let { value = $bindable('map') } = $props();
</script>

<div class="flex gap-3">
  <label
    class="flex-1 cursor-pointer rounded-lg border-2 p-4 text-center transition-colors
           {value === 'map' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}"
  >
    <input type="radio" bind:group={value} value="map" class="sr-only" />
    <div class="text-2xl mb-1">&#x1F5FA;</div>
    <div class="font-medium text-sm">Mapa (AI)</div>
    <div class="text-xs text-gray-500 mt-1">Illustrator .ai</div>
  </label>

  <label
    class="flex-1 cursor-pointer rounded-lg border-2 p-4 text-center transition-colors
           {value === 'idml' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}"
  >
    <input type="radio" bind:group={value} value="idml" class="sr-only" />
    <div class="text-2xl mb-1">&#x1F4F0;</div>
    <div class="font-medium text-sm">Casopis (IDML)</div>
    <div class="text-xs text-gray-500 mt-1">InDesign .idml</div>
  </label>
</div>
