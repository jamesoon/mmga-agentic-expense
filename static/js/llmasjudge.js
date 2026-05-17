(async function () {
  async function fetchJson(url) {
    try {
      const r = await fetch(url);
      if (!r.ok) return null;
      return await r.json();
    } catch (_e) {
      return null;
    }
  }

  function mkEl(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  function clearChildren(el) {
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  async function renderOverview() {
    const el = document.getElementById('overviewSummary');
    if (!el) return;
    const summary = await fetchJson('/llmasjudge/summary');
    clearChildren(el);
    if (!summary || !summary.summary) {
      el.appendChild(mkEl('div', '', 'No runs yet — click Run Full Eval to begin.'));
      return;
    }
    const s = summary.summary;
    const agentic = (100 * (s.agenticPct || 0)).toFixed(1);
    const b1 = (100 * (s.b1Pct || 0)).toFixed(1);
    const b2 = (100 * (s.b2Pct || 0)).toFixed(1);
    el.appendChild(mkEl('div', 'text-xl font-bold', 'Agentic ' + agentic + '%'));
    el.appendChild(mkEl('div', 'text-sm text-on-surface-variant', 'B1 ' + b1 + '%  ·  B2 ' + b2 + '%'));
  }

  async function renderBenchmarkChart() {
    const ctx = document.getElementById('benchmarkChart');
    if (!ctx || typeof Chart === 'undefined') return;
    const data = await fetchJson('/llmasjudge/analyses/latest');
    if (!data) return;
    const byBm = {};
    for (const j of data.judgments || []) {
      if (!byBm[j.benchmark_id]) byBm[j.benchmark_id] = {};
      byBm[j.benchmark_id][j.pipeline] = j.primary_judge_score;
    }
    const labels = Object.keys(byBm).sort();
    const pipelines = ['agentic', 'baseline_prompt', 'baseline_rules'];
    const sets = pipelines.map(function (p) {
      return { label: p, data: labels.map(function (l) { return byBm[l][p] || 0; }) };
    });
    new Chart(ctx, { type: 'bar', data: { labels: labels, datasets: sets } });
  }

  function renderRows(tbody, rows) {
    if (!tbody) return;
    clearChildren(tbody);
    for (const cells of rows) {
      const tr = document.createElement('tr');
      for (const c of cells) tr.appendChild(mkEl('td', 'py-1 pr-3', c));
      tbody.appendChild(tr);
    }
  }

  async function renderDisagreement() {
    const data = await fetchJson('/llmasjudge/analyses/latest');
    if (!data) return;

    const crossRows = (data.judgments || [])
      .filter(function (j) { return j.pipeline === 'agentic' && j.cross_modal_verdict != null; })
      .map(function (j) {
        return [
          j.benchmark_id,
          'image\u2192' + (j.verdict || ''),
          'text\u2192' + j.cross_modal_verdict,
          j.cross_modal_agree ? 'agree' : 'disagree',
        ];
      });
    renderRows(document.getElementById('crossModalBody'), crossRows);

    const verifierRows = (data.judgments || []).map(function (j) {
      return [
        j.benchmark_id + '/' + j.pipeline,
        'primary ' + Number(j.primary_judge_score).toFixed(2),
        'verifier ' + Number(j.verifier_judge_score).toFixed(2),
        j.verifier_agree ? 'ok' : 'disagree',
      ];
    });
    renderRows(document.getElementById('verifierBody'), verifierRows);

    const ol = document.getElementById('failureDigest');
    if (ol) {
      clearChildren(ol);
      for (const j of data.topDisagreement || []) {
        const li = document.createElement('li');
        li.className = 'text-sm';
        li.appendChild(mkEl('strong', '', j.benchmark_id));
        li.appendChild(document.createTextNode(
          ' (' + j.pipeline + ') \u2014 disagreementScore ' + Number(j.disagreement_score).toFixed(2),
        ));
        li.appendChild(document.createElement('br'));
        li.appendChild(mkEl('span', 'text-xs text-on-surface-variant', j.reasoning_digest || ''));
        ol.appendChild(li);
      }
    }
  }

  async function renderPlaygroundResult(el, payload) {
    clearChildren(el);
    if (!payload) {
      el.appendChild(mkEl('div', 'text-error text-sm', 'Scoring failed.'));
      return;
    }
    const verdict = String(payload.finalVerdict || payload.critiqueVerdict || 'unknown');
    const reasoning = String(payload.critiqueReasoning || '');
    el.appendChild(mkEl('div', 'text-lg font-bold', 'Verdict: ' + verdict));
    el.appendChild(mkEl('div', 'text-sm text-on-surface-variant mt-2', reasoning));
    const meta = mkEl('div', 'text-xs text-on-surface-variant mt-2',
      'Critique agrees: ' + (payload.critiqueAgrees ? 'yes' : 'no'));
    el.appendChild(meta);
  }

  function bindPlaygroundForm() {
    const form = document.getElementById('playgroundForm');
    if (!form) return;
    const resultEl = document.getElementById('playgroundResult');
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const fd = new FormData(form);
      const body = {
        receiptText: fd.get('receiptText') || '',
        agentVerdict: fd.get('agentVerdict') || 'requiresReview',
        userJustification: fd.get('userJustification') || '',
      };
      const r = await fetch('/llmasjudge/playground', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      let payload = null;
      try { payload = await r.json(); } catch (_e) { payload = null; }
      renderPlaygroundResult(resultEl, payload);
    });
  }

  function setStatus(text, isError) {
    let el = document.getElementById('runEvalStatus');
    if (!el) {
      const btn = document.getElementById('runEvalBtn');
      if (!btn || !btn.parentNode) return;
      el = document.createElement('div');
      el.id = 'runEvalStatus';
      el.className = 'text-xs mt-2';
      btn.parentNode.appendChild(el);
    }
    el.textContent = text || '';
    el.style.color = isError ? '#f87171' : '';
  }

  function bindRunButton() {
    const btn = document.getElementById('runEvalBtn');
    if (!btn) return;
    btn.addEventListener('click', async function () {
      btn.disabled = true;
      setStatus('Queuing eval run…', false);
      try {
        const r = await fetch('/llmasjudge/run', { method: 'POST' });
        let payload = null;
        try { payload = await r.json(); } catch (_e) {}
        if (!r.ok) {
          const bodyText = payload && payload.error
            ? payload.error
            : ('HTTP ' + r.status + (r.status === 429 ? ' — rate limit (1/hour). Wait and retry.' : ''));
          setStatus('Failed: ' + bodyText, true);
          return;
        }
        setStatus('Queued: runId=' + (payload && payload.runId) + ' — refreshing runs in 5s…', false);
        setTimeout(function () { renderRuns(); renderOverview(); }, 5000);
      } catch (e) {
        setStatus('Network error: ' + e.message, true);
      } finally {
        btn.disabled = false;
      }
    });
  }

  async function renderRuns() {
    const el = document.getElementById('runsContainer');
    if (!el) return;
    const data = await fetchJson('/llmasjudge/runs');
    clearChildren(el);
    const records = (data && data.records) || [];
    if (records.length === 0) {
      el.appendChild(mkEl('div', 'text-sm text-on-surface-variant', 'No runs yet.'));
      return;
    }
    const table = document.createElement('table');
    table.className = 'w-full text-sm';
    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    ['ID', 'Started', 'Finished', 'Status', 'Judge', 'Summary'].forEach(function (h) {
      headRow.appendChild(mkEl('th', 'text-left py-1 pr-3 text-xs uppercase tracking-widest text-on-surface-variant', h));
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    for (const r of records) {
      const tr = document.createElement('tr');
      tr.className = 'border-t border-outline-variant/20';
      const summary = r.summary_json || {};
      let summaryText = '';
      if (summary.error) {
        summaryText = 'error: ' + String(summary.error).slice(0, 80) + '…';
      } else if (typeof summary.agenticPct !== 'undefined') {
        summaryText = 'agentic ' + (100 * summary.agenticPct).toFixed(1) + '%';
      }
      const cells = [
        r.id,
        r.started_at ? r.started_at.replace('T', ' ').slice(0, 19) : '—',
        r.finished_at ? r.finished_at.replace('T', ' ').slice(0, 19) : '—',
        r.status,
        r.judge_model || '—',
        summaryText,
      ];
      for (const c of cells) tr.appendChild(mkEl('td', 'py-1 pr-3', c));
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    el.appendChild(table);
  }

  renderOverview();
  renderBenchmarkChart();
  renderDisagreement();
  renderRuns();
  bindPlaygroundForm();
  bindRunButton();
})();
