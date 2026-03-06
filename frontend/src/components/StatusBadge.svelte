<script>
  let { status = null } = $props();

  const styles = {
    OK: 'bg-green-100 text-green-800',
    OPRAVIT: 'bg-red-100 text-red-800',
    OVERIT: 'bg-yellow-100 text-yellow-800',
    PREVZIT: 'bg-gray-100 text-gray-700',
    CHYBI: 'bg-orange-100 text-orange-800',
  };
</script>

{#if status}
  <span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium {styles[status] || 'bg-gray-100 text-gray-600'}">
    {status}
  </span>
{:else}
  <span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-50 text-gray-400">&mdash;</span>
{/if}
