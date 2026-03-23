<script>
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';

  let summary = $state(null);
  let recent = $state([]);
  let loading = $state(true);
  let period = $state('today');

  // Period options → since parameter
  const periods = {
    today: () => new Date().toISOString().slice(0, 10),
    week: () => {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      return d.toISOString().slice(0, 10);
    },
    month: () => {
      const d = new Date();
      d.setMonth(d.getMonth() - 1);
      return d.toISOString().slice(0, 10);
    },
    all: () => null,
  };

  async function loadData() {
    loading = true;
    try {
      const since = periods[period]();
      const [s, r] = await Promise.all([
        api.tracesSummary(since),
        api.tracesRecent(50),
      ]);
      summary = s;
      recent = r;
    } catch (e) {
      notify('Chyba načítání traces: ' + e.message, 'error');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    period; // reactivity trigger
    loadData();
  });

  function fmtCost(v) {
    if (v >= 1) return '$' + v.toFixed(2);
    if (v >= 0.01) return '$' + v.toFixed(3);
    return '$' + v.toFixed(4);
  }
  function fmtTokens(v) {
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
    if (v >= 1_000) return (v / 1_000).toFixed(1) + 'K';
    return v.toString();
  }
  function fmtTime(v) {
    if (v >= 60) return (v / 60).toFixed(1) + ' min';
    return v.toFixed(1) + 's';
  }
  function modelShort(m) {
    if (m.includes('opus')) return 'Opus';
    if (m.includes('sonnet')) return 'Sonnet';
    if (m.includes('haiku')) return 'Haiku';
    return m.split('-').pop();
  }
  function timeAgo(iso) {
    const d = new Date(iso);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 60) return 'právě teď';
    if (s < 3600) return Math.floor(s / 60) + ' min';
    if (s < 86400) return Math.floor(s / 3600) + ' h';
    return Math.floor(s / 86400) + ' d';
  }
</script>

<div class="max-w-6xl mx-auto">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-xl font-bold text-gray-900">API Traces & Náklady</h1>
    <div class="flex items-center gap-2">
      {#each Object.keys(periods) as p}
        <button
          class="px-3 py-1 text-xs rounded-full transition-colors
                 {period === p ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
          onclick={() => { period = p; }}
        >
          {p === 'today' ? 'Dnes' : p === 'week' ? 'Týden' : p === 'month' ? 'Měsíc' : 'Vše'}
        </button>
      {/each}
      <button class="ml-2 px-3 py-1 text-xs bg-gray-100 text-gray-600 hover:bg-gray-200 rounded-full" onclick={loadData}>
        Obnovit
      </button>
    </div>
  </div>

  {#if loading}
    <div class="text-center py-16 text-gray-400">
      <div class="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if summary}
    <!-- Summary cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div class="bg-white rounded-lg border p-4">
        <div class="text-2xl font-bold text-gray-900">{summary.total_calls}</div>
        <div class="text-xs text-gray-500">API volání</div>
      </div>
      <div class="bg-white rounded-lg border p-4">
        <div class="text-2xl font-bold text-emerald-600">{fmtCost(summary.total_cost_usd)}</div>
        <div class="text-xs text-gray-500">Celková cena</div>
      </div>
      <div class="bg-white rounded-lg border p-4">
        <div class="text-2xl font-bold text-blue-600">{fmtTokens(summary.total_input_tokens + summary.total_output_tokens)}</div>
        <div class="text-xs text-gray-500">Tokeny (in+out)</div>
      </div>
      <div class="bg-white rounded-lg border p-4">
        <div class="text-2xl font-bold text-amber-600">{fmtTime(summary.total_latency_seconds)}</div>
        <div class="text-xs text-gray-500">Celková latence</div>
      </div>
    </div>

    <!-- By model & by module -->
    <div class="grid md:grid-cols-2 gap-6 mb-8">
      <!-- By model -->
      <div class="bg-white rounded-lg border">
        <div class="px-4 py-3 border-b">
          <h2 class="text-sm font-semibold text-gray-700">Podle modelu</h2>
        </div>
        <div class="divide-y">
          {#each Object.entries(summary.by_model) as [model, stats]}
            <div class="px-4 py-3 flex items-center justify-between">
              <div>
                <span class="text-sm font-medium">{modelShort(model)}</span>
                <span class="text-xs text-gray-400 ml-2">{stats.calls}x</span>
              </div>
              <div class="text-right">
                <span class="text-sm font-semibold text-emerald-600">{fmtCost(stats.cost_usd)}</span>
                <span class="text-xs text-gray-400 ml-2">{fmtTokens(stats.input_tokens + stats.output_tokens)} tok</span>
              </div>
            </div>
          {/each}
          {#if Object.keys(summary.by_model).length === 0}
            <div class="px-4 py-6 text-center text-sm text-gray-400">Žádná data</div>
          {/if}
        </div>
      </div>

      <!-- By module -->
      <div class="bg-white rounded-lg border">
        <div class="px-4 py-3 border-b">
          <h2 class="text-sm font-semibold text-gray-700">Podle modulu</h2>
        </div>
        <div class="divide-y">
          {#each Object.entries(summary.by_module).sort((a, b) => b[1].cost_usd - a[1].cost_usd) as [mod, stats]}
            <div class="px-4 py-3 flex items-center justify-between">
              <div>
                <span class="text-sm font-medium">{mod}</span>
                <span class="text-xs text-gray-400 ml-2">{stats.calls}x</span>
              </div>
              <div class="text-right">
                <span class="text-sm font-semibold text-emerald-600">{fmtCost(stats.cost_usd)}</span>
                <span class="text-xs text-gray-400 ml-2">{fmtTokens(stats.input_tokens + stats.output_tokens)} tok</span>
              </div>
            </div>
          {/each}
          {#if Object.keys(summary.by_module).length === 0}
            <div class="px-4 py-6 text-center text-sm text-gray-400">Žádná data</div>
          {/if}
        </div>
      </div>
    </div>

    <!-- Cache efficiency -->
    {#if summary.total_cache_read_tokens > 0}
      <div class="bg-white rounded-lg border p-4 mb-8">
        <h2 class="text-sm font-semibold text-gray-700 mb-2">Cache efektivita</h2>
        <div class="flex items-center gap-4">
          <div class="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
            {@const ratio = summary.total_cache_read_tokens / (summary.total_input_tokens || 1) * 100}
            <div class="bg-emerald-500 h-full rounded-full" style="width: {Math.min(ratio, 100)}%"></div>
          </div>
          <span class="text-sm text-gray-600">
            {fmtTokens(summary.total_cache_read_tokens)} cache hit
            ({(summary.total_cache_read_tokens / (summary.total_input_tokens || 1) * 100).toFixed(0)}%)
          </span>
        </div>
      </div>
    {/if}

    <!-- Recent traces table -->
    <div class="bg-white rounded-lg border">
      <div class="px-4 py-3 border-b">
        <h2 class="text-sm font-semibold text-gray-700">Poslední volání</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-500 border-b bg-gray-50">
              <th class="px-4 py-2">Kdy</th>
              <th class="px-4 py-2">Modul</th>
              <th class="px-4 py-2">Model</th>
              <th class="px-4 py-2 text-right">In</th>
              <th class="px-4 py-2 text-right">Out</th>
              <th class="px-4 py-2 text-right">Cena</th>
              <th class="px-4 py-2 text-right">Latence</th>
              <th class="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            {#each recent as t}
              <tr class="hover:bg-gray-50">
                <td class="px-4 py-2 text-gray-400" title={t.timestamp}>{timeAgo(t.timestamp)}</td>
                <td class="px-4 py-2 font-medium">{t.module}</td>
                <td class="px-4 py-2">
                  <span class="px-2 py-0.5 rounded text-xs
                    {t.model.includes('opus') ? 'bg-purple-100 text-purple-700' :
                     t.model.includes('haiku') ? 'bg-green-100 text-green-700' :
                     'bg-blue-100 text-blue-700'}">
                    {modelShort(t.model)}
                  </span>
                </td>
                <td class="px-4 py-2 text-right text-gray-600">{fmtTokens(t.input_tokens)}</td>
                <td class="px-4 py-2 text-right text-gray-600">{fmtTokens(t.output_tokens)}</td>
                <td class="px-4 py-2 text-right font-medium text-emerald-600">{fmtCost(t.cost_usd)}</td>
                <td class="px-4 py-2 text-right text-gray-500">{t.latency_seconds.toFixed(1)}s</td>
                <td class="px-4 py-2">
                  {#if t.success}
                    <span class="text-emerald-500">OK</span>
                  {:else}
                    <span class="text-red-500" title={t.error}>ERR</span>
                  {/if}
                </td>
              </tr>
            {/each}
            {#if recent.length === 0}
              <tr><td colspan="8" class="px-4 py-8 text-center text-gray-400">Žádné záznamy</td></tr>
            {/if}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Error rate -->
    {#if summary.error_count > 0}
      <div class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
        <span class="text-sm text-red-700">
          {summary.error_count} chyb z {summary.total_calls} volání
          ({(summary.error_count / summary.total_calls * 100).toFixed(1)}%)
        </span>
      </div>
    {/if}
  {:else}
    <div class="text-center py-16 text-gray-400">
      <p class="text-lg mb-2">Žádná data</p>
      <p class="text-sm">API traces se zaznamenávají automaticky při volání Claude API.</p>
    </div>
  {/if}
</div>
