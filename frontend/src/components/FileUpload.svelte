<script>
  let {
    accept = '.idml',
    label = 'Vyberte soubor',
    onupload = null,
    uploading = $bindable(false),
  } = $props();

  let dragOver = $state(false);
  let selectedFile = $state(null);

  function handleDragOver(e) {
    e.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }

  function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    const files = e.dataTransfer?.files;
    if (files?.length) {
      selectedFile = files[0];
      if (onupload) onupload(files[0]);
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (file) {
      selectedFile = file;
      if (onupload) onupload(file);
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
</script>

<div
  class="border-2 border-dashed rounded-xl p-6 text-center transition-colors
         {dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}"
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
  role="region"
  aria-label="File upload area"
>
  {#if uploading}
    <div class="text-blue-600">
      <div class="animate-spin inline-block w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mb-2"></div>
      <p class="text-sm">Nahravam...</p>
    </div>
  {:else if selectedFile}
    <div class="text-green-600">
      <p class="font-medium">{selectedFile.name}</p>
      <p class="text-sm text-gray-500">{formatSize(selectedFile.size)}</p>
    </div>
  {:else}
    <p class="text-gray-500 mb-2">{label}</p>
    <p class="text-xs text-gray-400 mb-3">Pretahnete sem nebo kliknete</p>
    <label class="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 text-sm">
      Vybrat soubor
      <input
        type="file"
        {accept}
        onchange={handleFileSelect}
        class="hidden"
      />
    </label>
  {/if}
</div>
