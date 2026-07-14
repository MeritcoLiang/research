const state = {
  currentRun: null,
  currentRunId: null,
  socket: null,
  activeTab: 'overview',
  config: null,
};

const el = (id) => document.getElementById(id);
const form = el('research-form');

window.addEventListener('DOMContentLoaded', async () => {
  bindEvents();
  el('as-of-date').value = new Date().toISOString().slice(0, 10);
  await checkHealth();
  await loadConfig();
  await refreshHistory();
});

function bindEvents() {
  form.addEventListener('submit', submitRun);
  el('sample-button').addEventListener('click', loadSample);
  el('refresh-history').addEventListener('click', refreshHistory);
  document.querySelectorAll('.tab').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeTab = button.dataset.tab;
      document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab === button));
      renderReport();
    });
  });
  el('provider').addEventListener('change', applyProviderModelDefault);
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    el('service-status').textContent = '服务在线';
    el('service-status').className = 'service-status online';
  } catch (error) {
    el('service-status').textContent = '服务离线';
    el('service-status').className = 'service-status offline';
  }
}

async function loadConfig() {
  try {
    state.config = await fetchJson('/api/config');
    el('provider').value = state.config.provider || 'azure';
    el('search-context').value = state.config.search_context_size || 'high';
    el('max-turns').value = String(state.config.max_turns || 30);
    applyProviderModelDefault();
  } catch (error) {
    showFormError(`加载配置失败：${error.message}`);
  }
}

function applyProviderModelDefault() {
  if (!state.config) return;
  const provider = el('provider').value;
  el('model').value = provider === 'azure'
    ? (state.config.azure_model || state.config.openai_model || '')
    : (state.config.openai_model || 'gpt-5.4');
}

function loadSample() {
  el('name').value = 'AWS Stone Ridge';
  el('county').value = 'Loudoun County';
  el('state').value = 'Virginia';
  el('aliases').value = 'Reeds Farm Lane';
  el('locations').value = 'Stone Ridge\nReeds Farm Lane';
  el('lookback-years').value = '8';
}

async function submitRun(event) {
  event.preventDefault();
  hideFormError();
  const button = el('submit-button');
  button.disabled = true;
  try {
    const payload = {
      research: {
        name: el('name').value.trim(),
        county: el('county').value.trim(),
        state: el('state').value.trim(),
        aliases: lines(el('aliases').value),
        location_hints: lines(el('locations').value),
        as_of_date: el('as-of-date').value,
        lookback_years: Number(el('lookback-years').value || 8),
      },
      runtime: {
        provider: el('provider').value,
        model: el('model').value.trim() || null,
        search_context_size: el('search-context').value,
        max_turns: Number(el('max-turns').value || 30),
      },
    };
    const created = await fetchJson('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    state.currentRunId = created.run_id;
    state.currentRun = {
      run_id: created.run_id,
      status: created.status,
      request: payload,
      events: [],
      report: null,
      error: null,
    };
    state.activeTab = 'overview';
    activateTab('overview');
    renderRun();
    connectRunSocket(created.run_id);
    await refreshHistory();
  } catch (error) {
    showFormError(error.message || String(error));
  } finally {
    button.disabled = false;
  }
}

async function refreshHistory() {
  const container = el('history-list');
  try {
    const payload = await fetchJson('/api/runs');
    const items = payload.items || [];
    if (!items.length) {
      container.innerHTML = '<div class="empty-state">暂无历史任务。</div>';
      return;
    }
    container.innerHTML = items.map((item) => `
      <button class="history-item ${item.run_id === state.currentRunId ? 'active' : ''}" data-run-id="${escapeHtml(item.run_id)}" type="button">
        <div class="history-item-top">
          <span class="history-name">${escapeHtml(item.name)}</span>
          <span class="mini-status">${escapeHtml(item.status)}</span>
        </div>
        <div class="history-meta">${escapeHtml(item.county)}, ${escapeHtml(item.state)} · ${escapeHtml(item.provider)}${item.stage ? ` · ${escapeHtml(item.stage)}` : ''}</div>
      </button>
    `).join('');
    container.querySelectorAll('.history-item').forEach((button) => {
      button.addEventListener('click', () => loadRun(button.dataset.runId));
    });
  } catch (error) {
    container.innerHTML = `<div class="error-box">加载历史失败：${escapeHtml(error.message)}</div>`;
  }
}

async function loadRun(runId) {
  try {
    closeSocket();
    state.currentRunId = runId;
    state.currentRun = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
    renderRun();
    await refreshHistory();
    if (!isTerminal(state.currentRun.status)) connectRunSocket(runId);
  } catch (error) {
    showFormError(`加载任务失败：${error.message}`);
  }
}

function connectRunSocket(runId) {
  closeSocket();
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${encodeURIComponent(runId)}`);
  state.socket = socket;
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'snapshot') state.currentRun = payload.run;
      if (payload.type === 'event') state.currentRun = payload.run;
      if (payload.type === 'error') throw new Error(payload.message);
      renderRun();
      if (state.currentRun && isTerminal(state.currentRun.status)) refreshHistory();
    } catch (error) {
      showFormError(`WebSocket 消息错误：${error.message}`);
    }
  };
  socket.onerror = () => showFormError('WebSocket 连接失败；可以从历史任务重新载入状态。');
  socket.onclose = () => {
    if (state.socket === socket) state.socket = null;
  };
}

function closeSocket() {
  if (state.socket) state.socket.close();
  state.socket = null;
}

function renderRun() {
  const run = state.currentRun;
  if (!run) return;
  const request = run.request.research;
  el('run-kicker').textContent = run.run_id;
  el('run-title').textContent = request.name;
  el('run-subtitle').textContent = `${request.county}, ${request.state} · 截止 ${request.as_of_date}`;
  const badge = el('run-status');
  badge.textContent = run.status;
  badge.className = `status-badge ${run.status}`;

  const hasReport = Boolean(run.report);
  for (const [id, extension] of [['download-json', 'json'], ['download-md', 'md']]) {
    const link = el(id);
    link.classList.toggle('disabled', !hasReport);
    link.href = hasReport ? `/api/runs/${encodeURIComponent(run.run_id)}/report.${extension}` : '#';
  }
  renderProgress();
  renderReport();
}

function renderProgress() {
  const run = state.currentRun;
  const container = el('progress-list');
  if (!run || !(run.events || []).length) {
    container.innerHTML = '<div class="empty-state">等待后端启动研究任务。</div>';
    return;
  }
  container.innerHTML = run.events.map((event) => `
    <div class="progress-item ${event.kind === 'error' ? 'error' : event.kind === 'completed' ? 'completed' : ''}">
      <div class="progress-message">${escapeHtml(event.message)}</div>
      <div class="progress-time">#${event.sequence} · ${formatTime(event.timestamp)} · ${escapeHtml(event.kind)}</div>
    </div>
  `).join('');
  container.scrollTop = container.scrollHeight;
}

function renderReport() {
  const container = el('report-content');
  const run = state.currentRun;
  if (!run) return;
  if (run.status === 'error') {
    container.innerHTML = `<div class="error-box"><strong>任务失败</strong><br>${escapeHtml(run.error || '未知错误')}</div>`;
    return;
  }
  if (!run.report) {
    container.innerHTML = `
      <div class="report-placeholder">
        <div class="placeholder-icon">◌</div>
        <h3>${run.status === 'running' ? '研究正在进行' : '等待任务启动'}</h3>
        <p>Web Search、证据冲突处理和结构化报告生成可能需要多个 Agent turn。</p>
      </div>`;
    return;
  }
  const renderers = {
    overview: renderOverview,
    workstreams: renderWorkstreams,
    timeline: renderTimeline,
    sources: renderSources,
    json: renderJson,
  };
  container.innerHTML = renderers[state.activeTab](run.report);
}

function renderOverview(report) {
  const latest = report.latest_verified_event;
  return `
    <div class="summary-hero">
      <div class="summary-stage">${escapeHtml(report.current_stage)}</div>
      <h3>${escapeHtml(report.identity.canonical_name)}</h3>
      <p>${escapeHtml(report.current_status)}</p>
      <div class="metric-row">
        <div class="metric"><div class="metric-label">Confidence</div><div class="metric-value">${percent(report.confidence)}</div></div>
        <div class="metric"><div class="metric-label">Sources</div><div class="metric-value">${report.sources.length}</div></div>
        <div class="metric"><div class="metric-label">Timeline events</div><div class="metric-value">${report.timeline.length}</div></div>
      </div>
    </div>
    <div class="section-grid" style="margin-top:.75rem">
      <div class="status-card"><h3>最近已核实事件</h3>${latest ? `<div class="confidence">${escapeHtml(latest.event_date)} · ${escapeHtml(latest.stage)}</div><p>${escapeHtml(latest.summary)}</p>` : '<p>尚未找到足够证据。</p>'}</div>
      <div class="status-card"><h3>下一预期里程碑</h3><p>${escapeHtml(report.next_expected_milestone || '尚未判断')}</p></div>
      <div class="status-card"><h3>身份线索</h3><ul>${listItems([
        ...report.identity.aliases.map((x) => `别名：${x}`),
        ...report.identity.owner_llcs.map((x) => `LLC：${x}`),
        ...report.identity.addresses.map((x) => `地址：${x}`),
        ...report.identity.case_numbers.map((x) => `Case：${x}`),
      ], '未确认新的身份标识')}</ul></div>
      <div class="status-card"><h3>研穵缺口</h3><ul>${listItems([...report.unresolved_questions, ...report.research_gaps], '无重大缺口')}</ul></div>
    </div>`;
}

function renderWorkstreams(report) {
  const sections = [
    ['规划与审批', report.approval_status],
    ['建设', report.construction_status],
    ['电力与输电', report.power_status],
    ['环境许可', report.environmental_status],
    ['基础设施', report.infrastructure_status],
    ['法律与社区', report.legal_and_community_status],
  ];
  return `<div class="section-grid">${sections.map(([title, section]) => `
    <div class="status-card">
      <h3>${title}</h3>
      <div class="confidence">${percent(section.confidence)}</div>
      <p>${escapeHtml(section.status)}</p>
      <strong>已核实</strong><ul>${listItems(section.verified_facts, '暂无')}</ul>
      <strong>待确认</strong><ul>${listItems(section.pending_items, '暂无')}</ul>
    </div>`).join('')}</div>`;
}

function renderTimeline(report) {
  if (!report.timeline.length) return '<div class="empty-state">没有可验证时间线。</div>';
  return `<div class="timeline">${report.timeline.map((event) => `
    <div class="timeline-item">
      <div class="timeline-date">${escapeHtml(event.event_date)} · ${escapeHtml(event.stage)}${event.is_inference ? ' · 推断' : ''}</div>
      <div class="timeline-title">${escapeHtml(event.event_type)} / ${escapeHtml(event.status)}</div>
      <div class="timeline-summary">${escapeHtml(event.summary)}</div>
    </div>`).join('')}</div>`;
}

function renderSources(report) {
  if (!report.sources.length) return '<div class="empty-state">报告没有来源记录。</div>';
  return `<div class="source-list">${report.sources.map((source) => `
    <div class="source-card">
      <a href="${escapeAttribute(source.url)}" target="_blank" rel="noreferrer">[${escapeHtml(source.authority_grade)}] ${escapeHtml(source.title)}</a>
      <div class="source-meta">${escapeHtml(source.publisher)} · ${escapeHtml(source.source_type)} · ${percent(source.confidence)}${source.event_date ? ` · 事件 ${escapeHtml(source.event_date)}` : ''}</div>
      <div class="source-note">${escapeHtml(source.evidence_note)}</div>
    </div>`).join('')}</div>`;
}

function renderJson(report) {
  return `<pre>${escapeHtml(JSON.stringify(report, null, 2))}</pre>`;
}

function activateTab(name) {
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === name));
}

function listItems(items, fallback) {
  const unique = [...new Set((items || []).filter(Boolean))];
  return unique.length ? unique.map((item) => `<li>${escapeHtml(item)}</li>`).join('') : `<li>${escapeHtml(fallback)}</li>`;
}

function lines(value) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function formatTime(value) {
  try { return new Date(value).toLocaleString(); } catch { return value || ''; }
}

function isTerminal(status) {
  return status === 'completed' || status === 'error';
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try { payload = await response.json(); } catch { /* non-json error */ }
  if (!response.ok) {
    const detail = payload?.detail;
    if (Array.isArray(detail)) throw new Error(detail.map((item) => item.msg).join('；'));
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}

function showFormError(message) {
  const box = el('form-error');
  box.hidden = false;
  box.textContent = message;
}

function hideFormError() {
  el('form-error').hidden = true;
  el('form-error').textContent = '';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
