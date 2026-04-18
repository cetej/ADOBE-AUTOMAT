<script>
  import { onMount } from 'svelte';
  import { currentProject } from '../stores/project.js';
  import { api } from '../lib/api.js';
  import { notify } from '../stores/notifications.js';

  let loading = $state(true);
  let reportsList = $state([]);
  let pipelineMd = $state('');
  let pipelineMeta = $state(null);
  let glossaryRuns = $state([]);
  let activeTab = $state('pipeline');
  let rawMode = $state(false);

  async function loadAll() {
    if (!$currentProject) return;
    loading = true;
    try {
      const list = await api.listReports($currentProject.id);
      reportsList = list.reports || [];

      const hasPipeline = reportsList.some(r => r.id === 'pipeline');
      if (hasPipeline) {
        try {
          const pr = await api.getPipelineReport($currentProject.id);
          pipelineMd = pr.markdown || '';
          pipelineMeta = { updated_at: pr.updated_at, size_bytes: pr.size_bytes };
        } catch (e) {
          pipelineMd = '';
        }
      }

      const hasGlossary = reportsList.some(r => r.id === 'glossary-fixes');
      if (hasGlossary) {
        try {
          const gf = await api.getGlossaryFixes($currentProject.id);
          glossaryRuns = gf.runs || [];
        } catch (e) {
          glossaryRuns = [];
        }
      }
    } catch (e) {
      notify('Nelze načíst reporty: ' + e.message, 'error');
    }
    loading = false;
  }

  function downloadUrl(reportId) {
    const id = $currentProject?.id;
    if (!id) return '#';
    switch (reportId) {
      case 'pipeline': return api.pipelineReportDownloadUrl(id);
      case 'glossary-fixes': return api.glossaryFixesDownloadUrl(id);
      case 'corrector-suggestions': return api.correctorSuggestionsDownloadUrl(id);
      case 'pipeline-changes': return api.pipelineChangesDownloadUrl(id);
      default: return '#';
    }
  }

  function formatBytes(n) {
    if (!n) return '0 B';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
    return (n / (1024 * 1024)).toFixed(2) + ' MB';
  }

  function formatDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleString('cs-CZ');
    } catch {
      return iso;
    }
  }

  // Jednoduchý markdown → HTML parser (nadpisy, tabulky, seznamy, bold, odstavce)
  function renderMarkdown(md) {
    if (!md) return '';
    const lines = md.split('\n');
    const out = [];
    let i = 0;

    const escapeHtml = (s) => s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    const inline = (s) => {
      let t = escapeHtml(s);
      t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      t = t.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-gray-100 rounded text-xs">$1</code>');
      return t;
    };

    while (i < lines.length) {
      const line = lines[i];

      // H1-H3
      const h = line.match(/^(#{1,3})\s+(.+)$/);
      if (h) {
        const level = h[1].length;
        const cls = level === 1
          ? 'text-xl font-bold text-gray-900 mt-6 mb-3 pb-2 border-b border-gray-200'
          : level === 2
          ? 'text-lg font-semibold text-gray-800 mt-5 mb-2'
          : 'text-base font-semibold text-gray-700 mt-4 mb-2';
        out.push(`<h${level} class="${cls}">${inline(h[2])}</h${level}>`);
        i++; continue;
      }

      // Horizontal rule
      if (/^---+\s*$/.test(line)) {
        out.push('<hr class="my-4 border-gray-200" />');
        i++; continue;
      }

      // Tabulka: | a | b |\n|---|---|\n| ... |
      if (line.trim().startsWith('|') && i + 1 < lines.length && /^\|[\s\-:|]+\|\s*$/.test(lines[i + 1])) {
        const header = line.split('|').slice(1, -1).map(c => c.trim());
        const rows = [];
        i += 2;
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          rows.push(lines[i].split('|').slice(1, -1).map(c => c.trim()));
          i++;
        }
        let html = '<div class="overflow-x-auto my-3"><table class="min-w-full text-sm border border-gray-200 rounded">';
        html += '<thead class="bg-gray-50"><tr>';
        for (const h of header) html += `<th class="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">${inline(h)}</th>`;
        html += '</tr></thead><tbody>';
        for (const r of rows) {
          html += '<tr class="border-b border-gray-100 last:border-0">';
          for (const c of r) html += `<td class="px-3 py-2 text-gray-800 align-top">${inline(c)}</td>`;
          html += '</tr>';
        }
        html += '</tbody></table></div>';
        out.push(html);
        continue;
      }

      // Seznam
      if (/^\s*[-*]\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
          i++;
        }
        let html = '<ul class="list-disc list-inside space-y-1 my-2 text-sm text-gray-700">';
        for (const it of items) html += `<li>${inline(it)}</li>`;
        html += '</ul>';
        out.push(html);
        continue;
      }

      // Prázdný řádek
      if (line.trim() === '') {
        i++; continue;
      }

      // Odstavec
      const para = [line];
      i++;
      while (i < lines.length && lines[i].trim() !== '' && !/^(#|---|\|\s|\s*[-*]\s)/.test(lines[i])) {
        para.push(lines[i]);
        i++;
      }
      out.push(`<p class="text-sm text-gray-700 my-2 leading-relaxed">${inline(para.join(' '))}</p>`);
    }

    return out.join('\n');
  }

  onMount(() => {
    loadAll();
  });

  // Re-load pokud se změní projekt
  let lastProjectId = $state(null);
  $effect(() => {
    const pid = $currentProject?.id;
    if (pid && pid !== lastProjectId) {
      lastProjectId = pid;
      loadAll();
    }
  });
</script>

<div class="max-w-5xl mx-auto">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Reporty — tabulky oprav</h1>
    <button
      onclick={loadAll}
      class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      disabled={loading}
    >
      {loading ? 'Načítám…' : 'Obnovit'}
    </button>
  </div>

  {#if !$currentProject}
    <p class="text-gray-500">Žádný projekt není otevřen.</p>
  {:else if loading}
    <div class="text-center py-12 text-gray-500">
      <div class="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
      <p class="text-sm">Načítám reporty…</p>
    </div>
  {:else if reportsList.length === 0}
    <div class="bg-white border border-gray-200 rounded-lg p-8 text-center">
      <p class="text-gray-500 text-sm mb-2">Žádné reporty nejsou k dispozici.</p>
      <p class="text-gray-400 text-xs">Spusť pipeline v Editoru — po dokončení se zde objeví tabulky oprav.</p>
    </div>
  {:else}
    <!-- Dostupné reporty — kartičky s download -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
      {#each reportsList as r}
        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1 min-w-0">
              <div class="font-medium text-gray-900 text-sm truncate">{r.title}</div>
              <div class="text-xs text-gray-500 mt-0.5">
                {r.format.toUpperCase()} · {formatBytes(r.size_bytes)} · {formatDate(r.updated_at)}
              </div>
              {#if r.runs !== undefined}
                <div class="text-xs text-gray-600 mt-1">
                  {r.runs} běhů · {r.total_fixes} oprav celkem
                </div>
              {/if}
            </div>
            <a
              href={downloadUrl(r.id)}
              download
              class="ml-3 px-2.5 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Stáhnout
            </a>
          </div>
        </div>
      {/each}
    </div>

    <!-- Tabs: Pipeline vs Glossary -->
    <div class="border-b border-gray-200 mb-4">
      <div class="flex gap-1">
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
                 {activeTab === 'pipeline' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}"
          onclick={() => activeTab = 'pipeline'}
        >
          Pipeline report {pipelineMd ? '' : '(není)'}
        </button>
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
                 {activeTab === 'glossary' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}"
          onclick={() => activeTab = 'glossary'}
        >
          Glossary enforcer {glossaryRuns.length ? `(${glossaryRuns.length})` : '(není)'}
        </button>
      </div>
    </div>

    {#if activeTab === 'pipeline'}
      {#if !pipelineMd}
        <div class="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p class="text-sm text-gray-500">Pipeline report zatím neexistuje.</p>
          <p class="text-xs text-gray-400 mt-1">Spusť pipeline v Editoru a po dokončení obnov tuto stránku.</p>
        </div>
      {:else}
        <div class="flex items-center justify-between mb-3">
          <div class="text-xs text-gray-500">
            Vygenerováno: {formatDate(pipelineMeta?.updated_at)} · {formatBytes(pipelineMeta?.size_bytes)}
          </div>
          <label class="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
            <input type="checkbox" bind:checked={rawMode} class="rounded" />
            Zobrazit jako raw markdown
          </label>
        </div>
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          {#if rawMode}
            <pre class="text-xs text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">{pipelineMd}</pre>
          {:else}
            <div class="prose-custom">
              {@html renderMarkdown(pipelineMd)}
            </div>
          {/if}
        </div>
      {/if}
    {:else if activeTab === 'glossary'}
      {#if glossaryRuns.length === 0}
        <div class="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p class="text-sm text-gray-500">Glossary enforcer zatím neprovedl žádné substituce.</p>
          <p class="text-xs text-gray-400 mt-1">Log se plní při každém AI překladu — pokud termdb.db zná kanonický překlad a LLM vrátil jiný.</p>
        </div>
      {:else}
        <div class="space-y-4">
          {#each glossaryRuns.slice().reverse() as run, idx}
            <div class="bg-white border border-gray-200 rounded-lg p-4">
              <div class="flex items-center justify-between mb-3 pb-2 border-b border-gray-100">
                <div>
                  <div class="text-sm font-medium text-gray-900">Běh #{glossaryRuns.length - idx}</div>
                  <div class="text-xs text-gray-500">{formatDate(run.timestamp)}</div>
                </div>
                <div class="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded">
                  {run.fixes?.length || 0} oprav
                </div>
              </div>
              {#if run.fixes?.length}
                <div class="overflow-x-auto">
                  <table class="min-w-full text-sm">
                    <thead class="bg-gray-50">
                      <tr>
                        <th class="px-3 py-2 text-left font-medium text-gray-700 border-b">EN</th>
                        <th class="px-3 py-2 text-left font-medium text-gray-700 border-b">Bylo (LLM)</th>
                        <th class="px-3 py-2 text-left font-medium text-gray-700 border-b">Je (DB kanon)</th>
                        <th class="px-3 py-2 text-left font-medium text-gray-700 border-b">Element ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each run.fixes as fx}
                        <tr class="border-b border-gray-100 last:border-0">
                          <td class="px-3 py-2 text-gray-800 font-mono text-xs">{fx.en}</td>
                          <td class="px-3 py-2 text-red-600 line-through">{fx.was}</td>
                          <td class="px-3 py-2 text-green-700 font-medium">{fx.now}</td>
                          <td class="px-3 py-2 text-gray-500 text-xs font-mono">{fx.element_id}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .prose-custom :global(h1:first-child) {
    margin-top: 0;
  }
</style>
