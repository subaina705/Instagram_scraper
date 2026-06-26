const fmt = (n) => {
  if (n === null || n === undefined || n === '') return '-';
  const v = Number(n);
  return Number.isFinite(v) ? v.toLocaleString() : String(n);
};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));

// ---- Theme toggle ----
const html = document.documentElement;
const THEME_KEY = 'reel-metrics-theme';

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

// Load saved preference (or system default)
const saved = localStorage.getItem(THEME_KEY);
if (saved === 'light' || saved === 'dark') {
  applyTheme(saved);
} else {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(prefersDark ? 'dark' : 'light');
}

$('theme-toggle').addEventListener('click', () => {
  const current = html.getAttribute('data-theme');
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

// ---- Rest of original JS ----
let bulkResults = [];
let profileResults = [];
let profileMeta = null;
let singleComments = [];
let commentsPage = 1;
const COMMENTS_PER_PAGE = 15;

function isBulkMode() {
  return document.querySelector('input[name="single-mode"]:checked')?.value === 'bulk';
}

function updateSingleModeUI() {
  const bulk = isBulkMode();
  $('single-url-wrap').classList.toggle('hidden', bulk);
  $('bulk-csv-wrap').classList.toggle('hidden', !bulk);
  $('go-debug').classList.toggle('hidden', bulk);
  $('go-single').querySelector('.btn-label').textContent = bulk ? 'Process CSV' : 'Fetch metrics';
  $('results-single').classList.remove('show');
  $('results-bulk').classList.remove('show');
  showStatus($('status-single'), '', '');
}

document.querySelectorAll('input[name="single-mode"]').forEach(r => {
  r.addEventListener('change', updateSingleModeUI);
});

function csvEscape(val) {
  const s = val == null ? '' : String(val);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function buildResultsCsv(rows) {
  const headers = ['Reel URL', 'Views', 'Likes', 'Comments', 'Shares', 'Saves', 'Reposts', 'Upload Date', 'Processing Status', 'Error Message'];
  const lines = [headers.map(csvEscape).join(',')];
  for (const row of rows) {
    lines.push([row.url || row.reel_url, row.views ?? '', row.likes ?? '', row.comments ?? '', row.shares ?? '', row.saves ?? '', row.reposts ?? '', row.date ?? '', row.status, row.error ?? ''].map(csvEscape).join(','));
  }
  return lines.join('\n');
}

function downloadBulkCsv() {
  if (!bulkResults.length) return;
  const blob = new Blob([buildResultsCsv(bulkResults)], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `reel-metrics-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

$('download-csv').addEventListener('click', downloadBulkCsv);

function buildProfileReelsCsv(reels) {
  const headers = [
    'Reel URL', 'Shortcode', 'Reel Date', 'Reel Views', 'Reel Likes', 'Reel Comment Count',
    'Comment #', 'Comment User', 'Comment Date', 'Comment Likes', 'Is Reply', 'Comment Text',
  ];
  const lines = [headers.map(csvEscape).join(',')];
  for (const reel of reels) {
    const url = reel.shortcode ? `https://www.instagram.com/reel/${reel.shortcode}/` : '';
    const base = [url, reel.shortcode ?? '', reel.date ?? '', reel.views ?? '', reel.likes ?? '', reel.comments ?? ''];
    const comments = reel.reel_comments || [];
    if (!comments.length) {
      lines.push([...base, '', '', '', '', '', 'No comments'].map(csvEscape).join(','));
      continue;
    }
    comments.forEach((c, i) => {
      lines.push([
        ...base,
        i + 1,
        c.username ?? '',
        c.date ?? '',
        c.likes ?? '',
        c.is_reply ? 'Yes' : 'No',
        c.text ?? '',
      ].map(csvEscape).join(','));
    });
  }
  return lines.join('\n');
}

function downloadProfileCsv() {
  if (!profileResults.length) return;
  const username = profileMeta?.username || 'profile';
  const blob = new Blob([buildProfileReelsCsv(profileResults)], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `profile-reels-${username}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

$('download-profile-csv').addEventListener('click', downloadProfileCsv);

function renderBulkResults(data) {
  bulkResults = data.results || [];
  const summary = data.summary || {};
  $('b_total').textContent = summary.total ?? bulkResults.length;
  $('b_success').textContent = summary.successful ?? 0;
  $('b_failed').textContent = summary.failed ?? 0;

  const tbody = $('bulk-tbody');
  tbody.innerHTML = '';
  bulkResults.forEach((row, i) => {
    const ok = row.status === 'Success';
    const link = row.url || row.reel_url;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td class="url-cell"><a href="${esc(link)}" target="_blank" rel="noreferrer">${esc(link)}</a></td><td class="num">${fmt(row.views)}</td><td class="num">${fmt(row.likes)}</td><td class="num">${fmt(row.comments)}</td><td class="num">${fmt(row.shares)}</td><td class="num">${fmt(row.saves)}</td><td class="num">${fmt(row.reposts)}</td><td>${esc(row.date) || '-'}</td><td><span class="badge ${ok ? 'ok' : 'err'}">${esc(row.status)}</span></td><td class="err-cell">${esc(row.error) || '—'}</td>`;
    tbody.appendChild(tr);
  });
  $('results-bulk').classList.add('show');
}

document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.pane').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('pane-' + t.dataset.tab).classList.add('active');
  });
});

function setBtnLoading(btn, loading, idleText, loadingText) {
  btn.disabled = loading;
  const label = btn.querySelector('.btn-label');
  if (loading) {
    label.innerHTML = `<span class="spinner"></span>${loadingText || 'Processing…'}`;
  } else {
    label.textContent = idleText;
  }
}

function showStatus(el, kind, msg) {
  el.className = 'status ' + (kind ? (kind + ' show') : '');
  el.textContent = msg || '';
}

async function parseJsonResponse(r) {
  const ct = r.headers.get('content-type') || '';
  if (!ct.includes('application/json')) {
    if (r.status === 404) throw new Error('API endpoint not found. Restart the server (python test.py) and try again.');
    throw new Error(`Unexpected server response (HTTP ${r.status}). Restart the server and try again.`);
  }
  return r.json();
}

function setBulkProgress(current, total, percent, label) {
  const pct = Math.max(0, Math.min(100, percent ?? (total ? Math.round(current * 100 / total) : 0)));
  $('progress-fill').style.width = pct + '%';
  $('progress-count').textContent = `${current} / ${total}`;
  $('progress-pct').textContent = pct + '%';
  if (label) $('progress-label').textContent = label;
}

function truncateUrl(url, max = 72) {
  const s = String(url || '');
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

async function consumeBulkStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';
    for (const frame of frames) {
      if (!frame.trim()) continue;
      let event = 'message', data = '';
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim();
        else if (line.startsWith('data: ')) data = line.slice(6);
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
  if (buffer.trim()) {
    let event = 'message', data = '';
    for (const line of buffer.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7).trim();
      else if (line.startsWith('data: ')) data = line.slice(6);
    }
    if (data) onEvent(event, JSON.parse(data));
  }
}

function buildReelCommentsPanel(comments) {
  if (!comments || !comments.length) {
    return '<div class="reel-comments-panel"><p class="reel-comments-empty">No comments found for this reel.</p></div>';
  }
  const rows = comments.map((c, i) => {
    const userLabel = c.username
      ? `<span class="comment-user">@${esc(c.username)}${c.full_name ? ` <span>(${esc(c.full_name)})</span>` : ''}</span>`
      : '—';
    const prefix = c.is_reply ? '↳ ' : '';
    const rowClass = c.is_reply ? 'reel-comment-reply' : '';
    return `<tr class="${rowClass}"><td>${i + 1}</td><td>${userLabel}</td><td>${esc(c.date) || '—'}</td><td class="num">${fmt(c.likes)}</td><td class="comment-text">${prefix}${esc(c.text)}</td></tr>`;
  }).join('');
  return `<div class="reel-comments-panel">
    <div class="reel-comments-meta">${comments.length} comment${comments.length === 1 ? '' : 's'}</div>
    <div class="table-wrap reel-comments-table-wrap">
      <table class="reel-comments-table">
        <thead><tr><th>#</th><th>User</th><th>Date</th><th class="num">Likes</th><th>Comment</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

function toggleReelComments(btn) {
  const mainRow = btn.closest('tr');
  const detailRow = mainRow?.nextElementSibling;
  if (!detailRow?.classList.contains('reel-comments-row')) return;
  const open = detailRow.classList.toggle('show');
  const count = btn.dataset.count || '0';
  btn.textContent = open ? `Hide Comments (${count})` : `Show Comments (${count})`;
  btn.classList.toggle('active', open);
  if (open) detailRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

$('reels-tbody').addEventListener('click', (e) => {
  const btn = e.target.closest('.btn-show-comments');
  if (btn) toggleReelComments(btn);
});

function countProfileComments(reels) {
  return (reels || []).reduce((sum, r) => sum + (r.reel_comments?.length || 0), 0);
}

function renderProfileResults(data) {
  $('p_username').textContent = data.profile.username || '-';
  $('p_fullname').textContent = data.profile.full_name || '-';
  $('p_followers').textContent = fmt(data.profile.followers);
  $('p_following').textContent = fmt(data.profile.following);
  $('p_posts').textContent = fmt(data.profile.posts);
  const dr = data.date_range || {}, hasDates = dr.count > 0;
  $('p_oldest').textContent = hasDates ? dr.oldest_date : '—';
  $('p_oldest_full').textContent = hasDates ? `(${dr.oldest_display})` : '';
  $('p_latest').textContent = hasDates ? dr.newest_date : '—';
  $('p_latest_full').textContent = hasDates ? `(${dr.newest_display})` : '';
  $('p_span').textContent = hasDates ? (dr.span_days === 0 ? `Single day · ${dr.count} reel${dr.count === 1 ? '' : 's'} analyzed` : `${dr.span_days.toLocaleString()} day${dr.span_days === 1 ? '' : 's'} · ${dr.count} reels analyzed`) : '—';

  const tbody = $('reels-tbody');
  tbody.innerHTML = '';
  if (!data.reels.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="9" style="text-align:center;color:var(--muted);padding:24px;">No reels found for this profile.</td>`;
    tbody.appendChild(tr);
  }

  let totViews = 0, totLikes = 0, totComments = 0, totFetched = 0;
  data.reels.forEach((reel, i) => {
    totViews += (reel.views || 0);
    totLikes += (reel.likes || 0);
    totComments += (reel.comments || 0);
    const fetched = reel.comments_fetched ?? (reel.reel_comments?.length || 0);
    totFetched += fetched;
    const url = 'https://www.instagram.com/reel/' + reel.shortcode + '/';
    const comments = reel.reel_comments || [];

    const mainTr = document.createElement('tr');
    mainTr.className = 'reel-row';
    mainTr.innerHTML = `<td>${i + 1}</td><td>${reel.date || '-'}</td><td><a href="${url}" target="_blank" rel="noreferrer">${reel.shortcode}</a></td><td class="num">${fmt(reel.views)}</td><td class="num">${fmt(reel.likes)}</td><td class="num">${fmt(reel.comments)}</td><td class="num">${fmt(fetched)}</td><td>${esc((reel.caption || '').slice(0, 200))}</td><td><button type="button" class="btn-show-comments" data-count="${fetched}">Show Comments (${fetched})</button></td>`;
    tbody.appendChild(mainTr);

    const detailTr = document.createElement('tr');
    detailTr.className = 'reel-comments-row';
    detailTr.innerHTML = `<td colspan="9">${buildReelCommentsPanel(comments)}</td>`;
    tbody.appendChild(detailTr);
  });

  $('s_count').textContent = data.reels.length;
  $('s_views').textContent = fmt(totViews);
  $('s_likes').textContent = fmt(totLikes);
  $('s_comments').textContent = fmt(totComments);
  $('pc_count').textContent = fmt(totFetched);

  profileResults = data.reels || [];
  profileMeta = data.profile || null;
}

function renderCommentsPage() {
  const tbody = $('comments-tbody');
  const pagination = $('comments-pagination');
  tbody.innerHTML = '';

  if (!singleComments.length) {
    pagination.classList.remove('show');
    return;
  }

  const totalPages = Math.max(1, Math.ceil(singleComments.length / COMMENTS_PER_PAGE));
  if (commentsPage > totalPages) commentsPage = totalPages;
  if (commentsPage < 1) commentsPage = 1;

  const start = (commentsPage - 1) * COMMENTS_PER_PAGE;
  const pageItems = singleComments.slice(start, start + COMMENTS_PER_PAGE);

  pageItems.forEach((c, i) => {
    const tr = document.createElement('tr');
    if (c.is_reply) tr.classList.add('comment-reply');
    const userLabel = c.username
      ? `<span class="comment-user">@${esc(c.username)}${c.full_name ? ` <span>(${esc(c.full_name)})</span>` : ''}</span>`
      : '—';
    const prefix = c.is_reply ? '↳ ' : '';
    tr.innerHTML = `<td>${start + i + 1}</td><td>${userLabel}</td><td>${esc(c.date) || '—'}</td><td class="num">${fmt(c.likes)}</td><td class="comment-text">${prefix}${esc(c.text)}</td>`;
    tbody.appendChild(tr);
  });

  $('comments-page-info').textContent = `Page ${commentsPage} of ${totalPages}`;
  $('comments-prev').disabled = commentsPage <= 1;
  $('comments-next').disabled = commentsPage >= totalPages;
  pagination.classList.toggle('show', totalPages > 1);
}

function renderSingleComments(data) {
  const comments = data.reel_comments || [];
  singleComments = comments;
  commentsPage = 1;
  $('c_count').textContent = fmt(data.comments_fetched ?? comments.length);
  $('c_reported').textContent = fmt(data.comments);

  if (!comments.length) {
    const tbody = $('comments-tbody');
    tbody.innerHTML = '';
    let msg = 'No comments found for this reel.';
    if (data.comments_note === 'comments_disabled') msg = 'Comments are disabled on this reel.';
    else if (data.comments_note === 'comments_unavailable') msg = 'Comments are unavailable for this reel.';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="5" style="text-align:center;color:var(--muted);padding:24px;">${esc(msg)}</td>`;
    tbody.appendChild(tr);
    $('comments-pagination').classList.remove('show');
    return;
  }

  renderCommentsPage();
}

$('comments-prev').addEventListener('click', () => {
  if (commentsPage > 1) {
    commentsPage--;
    renderCommentsPage();
  }
});

$('comments-next').addEventListener('click', () => {
  const totalPages = Math.ceil(singleComments.length / COMMENTS_PER_PAGE);
  if (commentsPage < totalPages) {
    commentsPage++;
    renderCommentsPage();
  }
});

$('f-single').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (isBulkMode()) { await submitBulkCsv(); return; }
  const btn = $('go-single'), status = $('status-single'), results = $('results-single');
  showStatus(status, '', '');
  results.classList.remove('show');
  $('results-bulk').classList.remove('show');
  setBtnLoading(btn, true, 'Fetch metrics', 'Fetching…');
  const payload = { username: $('username').value.trim(), password: $('password').value, shortcode: $('shortcode').value.trim() };
  if (!payload.shortcode) { showStatus(status, 'err', 'Please enter a reel or post URL.'); setBtnLoading(btn, false, 'Fetch metrics'); return; }
  showStatus(status, 'ok', 'Fetching metrics and comments — this may take a moment for popular reels…');
  try {
    const r = await fetch('/api/fetch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await r.json();
    if (!r.ok || !data.ok) {
      showStatus(status, 'err', 'Error: ' + (data.error || ('HTTP ' + r.status)));
    } else {
      $('m_views').textContent = fmt(data.views);
      $('m_likes').textContent = fmt(data.likes);
      $('m_comments').textContent = fmt(data.comments);
      $('m_shares').textContent = fmt(data.shares);
      $('m_saves').textContent = fmt(data.saves);
      $('m_reposts').textContent = fmt(data.reposts);
      $('d_shortcode').textContent = data.shortcode;
      $('d_owner').textContent = data.owner || '-';
      $('d_date').textContent = data.date || '-';
      $('d_video').textContent = data.is_video ? 'Yes' : 'No';
      $('d_caption').textContent = data.caption || 'No Caption';
      const url = 'https://www.instagram.com/' + (data.is_video ? 'reel' : 'p') + '/' + data.shortcode + '/';
      const a = $('d_url'); a.href = url; a.textContent = url;
      renderSingleComments(data);
      results.classList.add('show');
      let statusMsg = `Metrics and ${data.comments_fetched ?? 0} comment${(data.comments_fetched ?? 0) === 1 ? '' : 's'} retrieved successfully.`;
      if (data.comments_note === 'partial') statusMsg += ' Some comments may be missing due to an API limit.';
      else if (data.comments_note === 'comments_disabled') statusMsg = 'Metrics retrieved. Comments are disabled on this reel.';
      else if (data.comments_note === 'comments_unavailable') statusMsg = 'Metrics retrieved. Comments could not be loaded.';
      showStatus(status, 'ok', statusMsg);
    }
  } catch (err) {
    showStatus(status, 'err', 'Network error: ' + err.message);
  } finally {
    setBtnLoading(btn, false, 'Fetch metrics');
  }
});

async function submitBulkCsv() {
  const btn = $('go-single'), status = $('status-single'), progress = $('progress-bulk');
  showStatus(status, '', '');
  $('results-single').classList.remove('show');
  $('results-bulk').classList.remove('show');
  bulkResults = [];
  const fileInput = $('csv-file'), file = fileInput.files?.[0];
  if (!file) { showStatus(status, 'err', 'Please select a CSV file with reel URLs.'); return; }
  const form = new FormData();
  form.append('username', $('username').value.trim());
  form.append('password', $('password').value);
  form.append('csv', file);
  setBtnLoading(btn, true, 'Process CSV', 'Processing…');
  progress.classList.add('show');
  setBulkProgress(0, 0, 0, 'Uploading CSV file…');
  showStatus(status, 'ok', 'Processing each URL in your file. Any failures will be listed in the results table.');
  let finalData = null;
  try {
    const r = await fetch('/api/bulk_fetch_stream', { method: 'POST', body: form });
    const ct = r.headers.get('content-type') || '';
    if (!r.ok || !ct.includes('text/event-stream')) {
      const data = await parseJsonResponse(r);
      showStatus(status, 'err', 'Error: ' + (data.error || ('HTTP ' + r.status)));
      progress.classList.remove('show');
      return;
    }
    await consumeBulkStream(r, (event, data) => {
      if (event === 'start') setBulkProgress(0, data.total, 0, `Found ${data.total} URL${data.total === 1 ? '' : 's'} in CSV`);
      else if (event === 'progress') {
        const row = data.row || {}, url = row.url || row.reel_url || '', statusWord = row.status === 'Success' ? 'done' : 'failed';
        setBulkProgress(data.current, data.total, data.percent, `Reel ${data.current} of ${data.total} ${statusWord} — ${truncateUrl(url)}`);
      } else if (event === 'error') throw new Error(data.error || 'Bulk processing failed.');
      else if (event === 'complete') { finalData = data; setBulkProgress(data.summary?.total ?? 0, data.summary?.total ?? 0, 100, 'All reels processed'); }
    });
    if (!finalData?.ok) {
      showStatus(status, 'err', 'Error: Processing did not complete.');
      progress.classList.remove('show');
    } else {
      renderBulkResults(finalData);
      const s = finalData.summary || {};
      showStatus(status, 'ok', `Finished — ${s.total ?? 0} URL(s) processed: ${s.successful ?? 0} succeeded, ${s.failed ?? 0} failed.`);
      setTimeout(() => progress.classList.remove('show'), 800);
    }
  } catch (err) {
    showStatus(status, 'err', 'Network error: ' + err.message);
    progress.classList.remove('show');
  } finally {
    setBtnLoading(btn, false, 'Process CSV');
    if (!finalData?.ok) { $('progress-fill').style.width = '0%'; $('progress-count').textContent = '0 / 0'; $('progress-pct').textContent = '0%'; }
  }
}

$('go-debug').addEventListener('click', async () => {
  const btn = $('go-debug'), box = $('debug-box'), label = btn.querySelector('.btn-label');
  btn.disabled = true; label.textContent = '…';
  box.style.display = 'none'; box.textContent = '';
  const payload = { username: $('username').value.trim(), password: $('password').value, shortcode: $('shortcode').value.trim() };
  try {
    const r = await fetch('/api/debug_node', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await r.json();
    box.style.display = 'block';
    if (!data.ok) {
      box.style.color = '#fca5a5'; box.textContent = 'Error: ' + data.error;
    } else {
      box.style.color = '';
      const fmtFields = (obj) => Object.entries(obj || {}).map(([k, v]) => `${k.padEnd(50)} = ${JSON.stringify(v)}`).join('\n') || '(none)';
      box.textContent = `Shortcode : ${data.shortcode}\nOwner     : @${data.owner}\niPhone API available : ${data.iphone_available ? 'YES' : 'NO'}\n${data.iphone_error ? `iPhone API error    : ${data.iphone_error}\n` : ''}\nChosen (what the UI will display):\n  likes    = ${data.chosen_likes}\n  comments = ${data.chosen_comments}\n  views    = ${data.chosen_views}\n\n--- GraphQL ("web" API) count fields ---\n${fmtFields(data.graphql_fields)}\n\n--- iPhone / private API count fields ---\n${fmtFields(data.iphone_fields)}`;
    }
  } catch (e) {
    box.style.display = 'block'; box.style.color = '#fca5a5'; box.textContent = 'Network error: ' + e.message;
  } finally {
    btn.disabled = false; label.textContent = 'Debug raw node';
  }
});

$('f-profile').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = $('go-profile'), status = $('status-profile'), results = $('results-profile');
  showStatus(status, '', '');
  results.classList.remove('show');
  profileResults = [];
  profileMeta = null;
  setBtnLoading(btn, true, 'Fetch profile reels', 'Fetching…');
  const limitStr = $('limit').value.trim();
  const payload = { username: $('username').value.trim(), password: $('password').value, target: $('target').value.trim(), limit: limitStr === '' ? 20 : parseInt(limitStr, 10) || 0 };
  if (!payload.target) { showStatus(status, 'err', 'Please enter an Instagram username or profile URL.'); setBtnLoading(btn, false, 'Fetch profile reels'); return; }
  showStatus(status, 'ok', 'Fetching reels and all comments for each reel — this may take several minutes for large profiles…');
  try {
    const r = await fetch('/api/profile_reels', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await r.json();
    if (!r.ok || !data.ok) {
      showStatus(status, 'err', 'Error: ' + (data.error || ('HTTP ' + r.status)));
    } else {
      renderProfileResults(data);
      results.classList.add('show');
      const totalComments = countProfileComments(data.reels);
      const resolvedNote = data.resolved_target ? ` (resolved target: @${data.resolved_target})` : '';
      showStatus(status, 'ok', `Fetched ${data.reels.length} reel${data.reels.length === 1 ? '' : 's'} and ${totalComments} comment${totalComments === 1 ? '' : 's'}${resolvedNote}.`);
    }
  } catch (err) {
    showStatus(status, 'err', 'Network error: ' + err.message);
  } finally {
    setBtnLoading(btn, false, 'Fetch profile reels');
  }
});
