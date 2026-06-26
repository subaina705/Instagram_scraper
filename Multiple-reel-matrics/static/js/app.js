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
let bulkErrors = [];
let singleComments = [];
let commentsPage = 1;
const COMMENTS_PER_PAGE = 15;
const BULK_TABLE_COLSPAN = 11;
const PROFILE_TABLE_COLSPAN = 9;

const bulkProgressEls = {
  wrap: $('progress-bulk'),
  fill: $('progress-fill'),
  count: $('progress-count'),
  pct: $('progress-pct'),
  label: $('progress-label'),
};

function parseInstagramUsernameOnly(value) {
  const raw = (value || '').trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw) || /instagram\.com/i.test(raw)) return null;
  const username = raw.replace(/^@+/, '').replace(/\/+$/, '');
  if (!username || !/^[A-Za-z0-9._]+$/.test(username)) return null;
  return username;
}

const profileStreamTabs = {
  profile: {
    results: [],
    errors: [],
    meta: null,
    context: 'profile',
    btnLabel: 'Fetch profile reels',
    csvPrefix: 'profile-reels',
    progressEls: {
      wrap: $('progress-profile'),
      fill: $('progress-profile-fill'),
      count: $('progress-profile-count'),
      pct: $('progress-profile-pct'),
      label: $('progress-profile-label'),
    },
    els: {
      status: $('status-profile'),
      results: $('results-profile'),
      tbody: $('reels-tbody'),
      errors: $('profile-errors'),
      btn: $('go-profile'),
      username: $('p_username'),
      fullname: $('p_fullname'),
      followers: $('p_followers'),
      following: $('p_following'),
      posts: $('p_posts'),
      oldest: $('p_oldest'),
      oldestFull: $('p_oldest_full'),
      latest: $('p_latest'),
      latestFull: $('p_latest_full'),
      span: $('p_span'),
      count: $('s_count'),
      failed: $('p_failed'),
      views: $('s_views'),
      likes: $('s_likes'),
      comments: $('s_comments'),
      pcCount: $('pc_count'),
    },
    getTarget: () => $('target').value.trim(),
    getLimit: () => $('limit').value.trim(),
    resolveTarget(raw) {
      if (!raw) {
        return { ok: false, msg: 'Please enter an Instagram username or profile URL.' };
      }
      return { ok: true, value: raw };
    },
  },
  matrices: {
    results: [],
    errors: [],
    meta: null,
    context: 'matrices',
    btnLabel: 'Fetch account matrices',
    csvPrefix: 'account-matrices',
    progressEls: {
      wrap: $('progress-matrices'),
      fill: $('progress-matrices-fill'),
      count: $('progress-matrices-count'),
      pct: $('progress-matrices-pct'),
      label: $('progress-matrices-label'),
    },
    els: {
      status: $('status-matrices'),
      results: $('results-matrices'),
      tbody: $('matrices-tbody'),
      errors: $('matrices-errors'),
      btn: $('go-matrices'),
      username: $('a_username'),
      fullname: $('a_fullname'),
      followers: $('a_followers'),
      following: $('a_following'),
      posts: $('a_posts'),
      oldest: $('a_oldest'),
      oldestFull: $('a_oldest_full'),
      latest: $('a_latest'),
      latestFull: $('a_latest_full'),
      span: $('a_span'),
      count: $('a_count'),
      failed: $('a_failed'),
      views: $('a_views'),
      likes: $('a_likes'),
      comments: $('a_comments'),
      pcCount: $('ac_count'),
    },
    getTarget: () => $('target-matrices').value.trim(),
    getLimit: () => $('limit-matrices').value.trim(),
    resolveTarget(raw) {
      const username = parseInstagramUsernameOnly(raw);
      if (!username) {
        return {
          ok: false,
          msg: 'Please enter a valid Instagram username (e.g. @username). Profile URLs and reel links are not accepted.',
        };
      }
      return { ok: true, value: username };
    },
  },
};

function csvEscape(val) {
  const s = val == null ? '' : String(val);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function buildReelsCommentsCsv(reels) {
  const headers = [
    'Reel URL', 'Shortcode', 'Reel Date', 'Reel Views', 'Reel Likes', 'Reel Comment Count',
    'Comments Fetched', 'Comment #', 'Comment User', 'Comment Date', 'Is Reply', 'Comment Text',
  ];
  const emptyReelCols = ['', '', '', '', '', '', ''];
  const lines = [headers.map(csvEscape).join(',')];

  reels.forEach((reel, reelIndex) => {
    if (reelIndex > 0) lines.push('');

    const url = reel.url || reel.reel_url || getReelUrl(reel);
    const fetched = reel.comments_fetched ?? (reel.reel_comments?.length || 0);
    const reelRow = [url, reel.shortcode ?? '', reel.date ?? '', reel.views ?? '', reel.likes ?? '', reel.comments ?? '', fetched];
    const comments = reel.reel_comments || [];

    if (!comments.length) {
      const note = reel.status === 'Failed' ? (reel.error || 'Failed') : 'No comments';
      lines.push([...reelRow, '', '', '', '', note].map(csvEscape).join(','));
      return;
    }

    comments.forEach((c, i) => {
      lines.push([
        ...(i === 0 ? reelRow : emptyReelCols),
        i + 1,
        c.username ?? '',
        c.date ?? '',
        c.is_reply ? 'Yes' : 'No',
        c.text ?? '',
      ].map(csvEscape).join(','));
    });
  });

  return lines.join('\n');
}

function buildResultsCsv(rows) {
  return buildReelsCommentsCsv(rows);
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
  return buildReelsCommentsCsv(reels);
}

function downloadProfileStreamCsv(tabKey) {
  const tab = profileStreamTabs[tabKey];
  if (!tab?.results.length) return;
  const username = tab.meta?.username || tabKey;
  const blob = new Blob([buildProfileReelsCsv(tab.results)], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${tab.csvPrefix}-${username}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

$('download-profile-csv').addEventListener('click', () => downloadProfileStreamCsv('profile'));
$('download-matrices-csv').addEventListener('click', () => downloadProfileStreamCsv('matrices'));

function renderErrorSummary(el, errors, title) {
  if (!errors.length) {
    el.classList.remove('show');
    el.innerHTML = '';
    return;
  }
  el.classList.add('show');
  const items = errors.map((r) => {
    const label = r.url || r.reel_url || r.shortcode || 'Unknown';
    return `<li><span class="error-url">${esc(label)}</span><span class="error-msg">${esc(r.error || 'Unknown error')}</span></li>`;
  }).join('');
  el.innerHTML = `<div class="section-title">${title} (${errors.length})</div><ul class="error-list">${items}</ul>`;
}

function renderBulkErrors() {
  renderErrorSummary($('bulk-errors'), bulkErrors, 'Failed URLs');
}

function renderProfileStreamErrors(tab) {
  renderErrorSummary(tab.els.errors, tab.errors, 'Failed reels');
}

function isProfileReelError(reel) {
  const caption = reel?.caption || '';
  return !reel?.shortcode || reel.shortcode === '?' || caption.startsWith('[error reading post:');
}

function updateBulkSummaryCounts(total, successful, failed) {
  $('b_total').textContent = total ?? bulkResults.length + bulkErrors.length;
  $('b_success').textContent = successful ?? bulkResults.length;
  $('b_failed').textContent = failed ?? bulkErrors.length;
}

function appendBulkRow(row, index) {
  const link = row.url || row.reel_url;
  const fetched = row.comments_fetched ?? (row.reel_comments?.length || 0);
  const comments = row.reel_comments || [];
  const loaded = fetched > 0;
  const tbody = $('bulk-tbody');
  const mainTr = document.createElement('tr');
  mainTr.className = 'reel-row';
  mainTr.innerHTML = `<td>${index + 1}</td><td class="url-cell"><a href="${esc(link)}" target="_blank" rel="noreferrer">${esc(link)}</a></td><td class="num">${fmt(row.views)}</td><td class="num">${fmt(row.likes)}</td><td class="num">${fmt(row.comments)}</td><td class="num">${fmt(row.shares)}</td><td class="num">${fmt(row.saves)}</td><td class="num">${fmt(row.reposts)}</td><td>${esc(row.date) || '-'}</td><td class="num bulk-fetched-cell">${fmt(fetched)}</td><td>${buildCommentActionButton(row, index, 'bulk')}</td>`;
  tbody.appendChild(mainTr);
  const detailTr = document.createElement('tr');
  detailTr.className = 'reel-comments-row';
  detailTr.innerHTML = buildCommentsDetailRow(BULK_TABLE_COLSPAN, comments, loaded);
  tbody.appendChild(detailTr);
}

function initBulkStreamUI(total) {
  bulkResults = [];
  bulkErrors = [];
  $('bulk-tbody').innerHTML = '';
  renderBulkErrors();
  updateBulkSummaryCounts(total, 0, 0);
  $('results-bulk').classList.add('show');
  bulkProgressEls.wrap.classList.add('show');
  setStreamProgress(bulkProgressEls, 0, total, 0, `Found ${total} URL${total === 1 ? '' : 's'} in CSV`);
}

function setProfileStreamHeader(tab, profile, dateRange) {
  tab.meta = profile || null;
  if (!profile) return;
  const { els } = tab;
  els.username.textContent = profile.username || '-';
  els.fullname.textContent = profile.full_name || '-';
  els.followers.textContent = fmt(profile.followers);
  els.following.textContent = fmt(profile.following);
  els.posts.textContent = fmt(profile.posts);
  if (dateRange) setProfileStreamDateRange(tab, dateRange);
}

function setProfileStreamDateRange(tab, dr) {
  const hasDates = dr && dr.count > 0;
  const { els } = tab;
  els.oldest.textContent = hasDates ? dr.oldest_date : '—';
  els.oldestFull.textContent = hasDates ? `(${dr.oldest_display})` : '';
  els.latest.textContent = hasDates ? dr.newest_date : '—';
  els.latestFull.textContent = hasDates ? `(${dr.newest_display})` : '';
  els.span.textContent = hasDates
    ? (dr.span_days === 0
      ? `Single day · ${dr.count} reel${dr.count === 1 ? '' : 's'} analyzed`
      : `${dr.span_days.toLocaleString()} day${dr.span_days === 1 ? '' : 's'} · ${dr.count} reels analyzed`)
    : '—';
}

function updateProfileStreamSummary(tab) {
  let totViews = 0, totLikes = 0, totComments = 0, totFetched = 0;
  tab.results.forEach((reel) => {
    totViews += reel.views || 0;
    totLikes += reel.likes || 0;
    totComments += reel.comments || 0;
    totFetched += reel.comments_fetched ?? (reel.reel_comments?.length || 0);
  });
  const { els } = tab;
  els.count.textContent = tab.results.length;
  els.failed.textContent = tab.errors.length;
  els.views.textContent = fmt(totViews);
  els.likes.textContent = fmt(totLikes);
  els.comments.textContent = fmt(totComments);
  els.pcCount.textContent = fmt(totFetched);
}

function getReelUrl(reel) {
  if (reel?.url || reel?.reel_url) return reel.url || reel.reel_url;
  const shortcode = reel?.shortcode;
  if (!shortcode || shortcode === '?') return '';
  const pt = (reel.product_type || '').toLowerCase();
  let segment = 'p';
  if (pt === 'clips') segment = 'reel';
  else if (pt === 'igtv') segment = 'tv';
  return `https://www.instagram.com/${segment}/${shortcode}/`;
}

function appendProfileStreamReelRow(tab, reel, index) {
  const tbody = tab.els.tbody;
  const emptyRow = tbody.querySelector('.empty-row');
  if (emptyRow) emptyRow.remove();

  const fetched = reel.comments_fetched ?? (reel.reel_comments?.length || 0);
  const comments = reel.reel_comments || [];
  const loaded = fetched > 0;
  const url = getReelUrl(reel);
  const linkCell = tab.context === 'matrices'
    ? `<td class="url-cell"><a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a></td>`
    : `<td><a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(reel.shortcode)}</a></td>`;

  const mainTr = document.createElement('tr');
  mainTr.className = 'reel-row';
  mainTr.innerHTML = `<td>${index + 1}</td><td>${reel.date || '-'}</td>${linkCell}<td class="num">${fmt(reel.views)}</td><td class="num">${fmt(reel.likes)}</td><td class="num">${fmt(reel.comments)}</td><td class="num">${fmt(fetched)}</td><td>${esc((reel.caption || '').slice(0, 200))}</td><td>${buildCommentActionButton(reel, index, tab.context)}</td>`;
  tbody.appendChild(mainTr);

  const detailTr = document.createElement('tr');
  detailTr.className = 'reel-comments-row';
  detailTr.innerHTML = buildCommentsDetailRow(PROFILE_TABLE_COLSPAN, comments, loaded);
  tbody.appendChild(detailTr);
}

function initProfileStreamUI(tab, expected) {
  tab.results = [];
  tab.errors = [];
  tab.els.tbody.innerHTML = '';
  renderProfileStreamErrors(tab);
  tab.els.count.textContent = '0';
  tab.els.failed.textContent = '0';
  tab.els.views.textContent = '0';
  tab.els.likes.textContent = '0';
  tab.els.comments.textContent = '0';
  tab.els.pcCount.textContent = '0';
  tab.els.results.classList.add('show');
  setStreamProgress(
    tab.progressEls,
    0,
    expected || 0,
    0,
    expected ? `Found ${expected} reel${expected === 1 ? '' : 's'} — loading…` : 'Loading reels…',
  );
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

function setStreamProgress(els, current, total, percent, label) {
  const pct = Math.max(0, Math.min(100, percent ?? (total ? Math.round(current * 100 / total) : 0)));
  els.fill.style.width = pct + '%';
  els.count.textContent = total ? `${current} / ${total}` : `${current}`;
  els.pct.textContent = pct + '%';
  if (label) els.label.textContent = label;
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

function buildCommentActionButton(reel, index, context) {
  const fetched = reel.comments_fetched ?? (reel.reel_comments?.length || 0);
  const shortcode = reel.shortcode || '';
  const url = getReelUrl(reel);
  if (fetched > 0) {
    return `<button type="button" class="btn-show-comments" data-count="${fetched}" data-index="${index}" data-context="${context}">Show Comments (${fetched})</button>`;
  }
  if (context === 'bulk' && reel.status !== 'Success') return '—';
  if (!shortcode && !url) return '—';
  return `<button type="button" class="btn-load-comments" data-shortcode="${esc(shortcode)}" data-url="${esc(url)}" data-index="${index}" data-context="${context}">Load Comments</button>`;
}

function buildCommentsDetailRow(colspan, comments, loaded) {
  const panel = loaded
    ? buildReelCommentsPanel(comments)
    : '<div class="reel-comments-panel"><p class="reel-comments-empty">Click <strong>Load Comments</strong> to fetch comments for this reel.</p></div>';
  return `<td colspan="${colspan}">${panel}</td>`;
}

async function fetchReelComments(shortcodeOrUrl) {
  const payload = {
    username: $('username').value.trim(),
    password: $('password').value,
    shortcode: shortcodeOrUrl,
  };
  const r = await fetch('/api/reel_comments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await parseJsonResponse(r);
  if (!r.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${r.status}`);
  }
  return data;
}

function getStreamTabResults(context) {
  if (context === 'bulk') return bulkResults;
  return profileStreamTabs[context]?.results || null;
}

function updateProfileStreamCommentTotals(tab) {
  let totFetched = 0;
  tab.results.forEach((r) => {
    totFetched += r.comments_fetched ?? (r.reel_comments?.length || 0);
  });
  tab.els.pcCount.textContent = fmt(totFetched);
}

async function handleLoadComments(btn) {
  const index = parseInt(btn.dataset.index, 10);
  const context = btn.dataset.context;
  const shortcode = btn.dataset.shortcode;
  const url = btn.dataset.url;
  const reelRef = context === 'bulk' ? bulkResults[index] : getStreamTabResults(context)?.[index];

  btn.disabled = true;
  btn.textContent = 'Loading…';

  try {
    const data = await fetchReelComments(shortcode || url);
    const comments = data.reel_comments || [];
    const fetched = data.comments_fetched ?? comments.length;

    if (reelRef) {
      reelRef.reel_comments = comments;
      reelRef.comments_fetched = fetched;
      reelRef.comments_note = data.comments_note;
      if (data.shortcode) reelRef.shortcode = data.shortcode;
      if (data.url) reelRef.url = data.url;
      if (data.reel_url) reelRef.reel_url = data.reel_url;
    }

    const mainRow = btn.closest('tr');
    const detailRow = mainRow?.nextElementSibling;
    if (detailRow?.classList.contains('reel-comments-row')) {
      detailRow.innerHTML = buildCommentsDetailRow(detailRow.children[0]?.colSpan || 9, comments, true);
      detailRow.classList.add('show');
    }

    const showBtn = document.createElement('button');
    showBtn.type = 'button';
    showBtn.className = 'btn-show-comments active';
    showBtn.dataset.count = fetched;
    showBtn.dataset.index = index;
    showBtn.dataset.context = context;
    showBtn.textContent = `Hide Comments (${fetched})`;
    btn.replaceWith(showBtn);

    if (context === 'profile' || context === 'matrices') {
      const tab = profileStreamTabs[context];
      updateProfileStreamCommentTotals(tab);
      const fetchedCell = mainRow?.querySelector('td:nth-child(7)');
      if (fetchedCell) fetchedCell.textContent = fmt(fetched);
    } else if (context === 'bulk') {
      const fetchedCell = mainRow?.querySelector('.bulk-fetched-cell');
      if (fetchedCell) fetchedCell.textContent = fmt(fetched);
    }
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Load Comments';
    alert('Failed to load comments: ' + err.message);
  }
}

function handleReelTableClick(e) {
  const loadBtn = e.target.closest('.btn-load-comments');
  if (loadBtn) {
    handleLoadComments(loadBtn);
    return;
  }
  const showBtn = e.target.closest('.btn-show-comments');
  if (showBtn) toggleReelComments(showBtn);
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

$('reels-tbody').addEventListener('click', handleReelTableClick);
$('matrices-tbody').addEventListener('click', handleReelTableClick);
$('bulk-tbody').addEventListener('click', handleReelTableClick);

function countProfileComments(reels) {
  return (reels || []).reduce((sum, r) => sum + (r.reel_comments?.length || 0), 0);
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
  const btn = $('go-single'), status = $('status-single'), results = $('results-single');
  showStatus(status, '', '');
  results.classList.remove('show');
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
      const url = data.url || data.reel_url || getReelUrl(data);
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

$('f-bulk').addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitBulkCsv();
});

async function submitBulkCsv() {
  const btn = $('go-bulk'), status = $('status-bulk');
  showStatus(status, '', '');
  $('results-bulk').classList.remove('show');
  const fileInput = $('csv-file'), file = fileInput.files?.[0];
  if (!file) { showStatus(status, 'err', 'Please select a CSV file with reel URLs.'); return; }
  const form = new FormData();
  form.append('username', $('username').value.trim());
  form.append('password', $('password').value);
  form.append('csv', file);
  setBtnLoading(btn, true, 'Process CSV', 'Processing…');
  showStatus(status, 'ok', 'Processing URLs — reels appear in the table as they finish. Use Load Comments per row when needed.');
  let streamTotal = 0;
  let streamDone = false;
  try {
    const r = await fetch('/api/bulk_fetch_stream', { method: 'POST', body: form });
    const ct = r.headers.get('content-type') || '';
    if (!r.ok || !ct.includes('text/event-stream')) {
      const data = await parseJsonResponse(r);
      showStatus(status, 'err', 'Error: ' + (data.error || ('HTTP ' + r.status)));
      bulkProgressEls.wrap.classList.remove('show');
      return;
    }
    await consumeBulkStream(r, (event, data) => {
      if (event === 'start') {
        streamTotal = data.total || 0;
        initBulkStreamUI(streamTotal);
      } else if (event === 'progress') {
        const row = data.row || {};
        const url = row.url || row.reel_url || '';
        const statusWord = row.status === 'Success' ? 'done' : 'failed';
        setStreamProgress(
          bulkProgressEls,
          data.current,
          data.total,
          data.percent,
          `Reel ${data.current} of ${data.total} ${statusWord} — ${truncateUrl(url)}`,
        );
        if (row.status === 'Success') {
          bulkResults.push(row);
          appendBulkRow(row, bulkResults.length - 1);
        } else {
          bulkErrors.push(row);
          renderBulkErrors();
        }
        updateBulkSummaryCounts(data.total, data.successful, data.failed);
      } else if (event === 'error') {
        throw new Error(data.error || 'Bulk processing failed.');
      } else if (event === 'complete') {
        streamDone = true;
        setStreamProgress(
          bulkProgressEls,
          data.summary?.total ?? streamTotal,
          data.summary?.total ?? streamTotal,
          100,
          'All reels processed',
        );
      }
    });
    if (!streamDone) {
      showStatus(status, 'err', 'Error: Processing did not complete.');
      bulkProgressEls.wrap.classList.remove('show');
    } else {
      const s = { total: bulkResults.length + bulkErrors.length, successful: bulkResults.length, failed: bulkErrors.length };
      showStatus(status, 'ok', `Finished — ${s.total} URL(s): ${s.successful} succeeded, ${s.failed} failed.`);
      setTimeout(() => bulkProgressEls.wrap.classList.remove('show'), 800);
    }
  } catch (err) {
    showStatus(status, 'err', 'Network error: ' + err.message);
    bulkProgressEls.wrap.classList.remove('show');
  } finally {
    setBtnLoading(btn, false, 'Process CSV');
    if (!streamDone) {
      bulkProgressEls.fill.style.width = '0%';
      bulkProgressEls.count.textContent = '0 / 0';
      bulkProgressEls.pct.textContent = '0%';
    }
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

$('f-profile').addEventListener('submit', (e) => {
  e.preventDefault();
  submitProfileReelsStream('profile');
});

$('f-matrices').addEventListener('submit', (e) => {
  e.preventDefault();
  submitProfileReelsStream('matrices');
});

async function submitProfileReelsStream(tabKey) {
  const tab = profileStreamTabs[tabKey];
  const { els, progressEls, btnLabel } = tab;
  const btn = els.btn;
  const status = els.status;
  showStatus(status, '', '');
  els.results.classList.remove('show');
  tab.results = [];
  tab.errors = [];
  tab.meta = null;
  setBtnLoading(btn, true, btnLabel, 'Fetching…');

  const targetRaw = tab.getTarget();
  const resolved = tab.resolveTarget(targetRaw);
  if (!resolved.ok) {
    showStatus(status, 'err', resolved.msg);
    setBtnLoading(btn, false, btnLabel);
    progressEls.wrap.classList.remove('show');
    return;
  }

  const limitStr = tab.getLimit();
  const payload = {
    username: $('username').value.trim(),
    password: $('password').value,
    target: resolved.value,
    limit: limitStr === '' ? 20 : parseInt(limitStr, 10) || 0,
  };

  progressEls.wrap.classList.add('show');
  setStreamProgress(progressEls, 0, 0, 0, 'Connecting…');
  showStatus(status, 'ok', 'Loading reels — each row appears as soon as it is fetched. Click Load Comments when you need comment text.');
  let streamDone = false;
  let resolvedTarget = '';
  try {
    const r = await fetch('/api/profile_reels_stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const ct = r.headers.get('content-type') || '';
    if (!r.ok || !ct.includes('text/event-stream')) {
      const data = await parseJsonResponse(r);
      showStatus(status, 'err', 'Error: ' + (data.error || ('HTTP ' + r.status)));
      progressEls.wrap.classList.remove('show');
      return;
    }
    await consumeBulkStream(r, (event, data) => {
      if (event === 'start') {
        resolvedTarget = data.resolved_target || '';
        const expected = data.expected || data.total || 0;
        initProfileStreamUI(tab, expected);
        setProfileStreamHeader(tab, data.profile, null);
        setStreamProgress(
          progressEls,
          0,
          expected,
          0,
          `Loading reels for @${data.profile?.username || resolvedTarget}…`,
        );
      } else if (event === 'reel') {
        const reel = data.reel || {};
        const total = data.total || data.expected || data.current || tab.results.length + tab.errors.length + 1;
        if (isProfileReelError(reel)) {
          tab.errors.push({
            shortcode: reel.shortcode || '—',
            error: reel.caption?.replace(/^\[error reading post:\s*/i, '').replace(/\]$/, '') || 'Failed to read reel',
          });
          renderProfileStreamErrors(tab);
        } else {
          tab.results.push(reel);
          appendProfileStreamReelRow(tab, reel, tab.results.length - 1);
        }
        updateProfileStreamSummary(tab);
        const pct = total ? Math.round((data.current / total) * 100) : 0;
        setStreamProgress(
          progressEls,
          data.current,
          total,
          pct,
          `Loaded reel ${data.current}: ${reel.shortcode || '—'}`,
        );
      } else if (event === 'complete') {
        streamDone = true;
        setProfileStreamDateRange(tab, data.date_range);
        const total = data.total || tab.results.length + tab.errors.length;
        setStreamProgress(progressEls, total, total, 100, 'All reels loaded');
        if (!tab.results.length && !tab.errors.length) {
          const tr = document.createElement('tr');
          tr.className = 'empty-row';
          tr.innerHTML = `<td colspan="${PROFILE_TABLE_COLSPAN}" style="text-align:center;color:var(--muted);padding:24px;">No reels found for this profile.</td>`;
          tab.els.tbody.appendChild(tr);
        }
      } else if (event === 'error') {
        throw new Error(data.error || 'Profile fetch failed.');
      }
    });
    if (!streamDone) {
      showStatus(status, 'err', 'Error: Profile fetch did not complete.');
      progressEls.wrap.classList.remove('show');
    } else {
      const note = resolvedTarget ? ` (resolved target: @${resolvedTarget})` : '';
      const failNote = tab.errors.length ? `, ${tab.errors.length} failed` : '';
      showStatus(
        status,
        'ok',
        `Loaded ${tab.results.length} reel${tab.results.length === 1 ? '' : 's'}${failNote}${note}. Use Load Comments per row for comment text.`,
      );
      setTimeout(() => progressEls.wrap.classList.remove('show'), 800);
    }
  } catch (err) {
    showStatus(status, 'err', 'Network error: ' + err.message);
    progressEls.wrap.classList.remove('show');
  } finally {
    setBtnLoading(btn, false, btnLabel);
    if (!streamDone) {
      progressEls.fill.style.width = '0%';
      progressEls.count.textContent = '0 / 0';
      progressEls.pct.textContent = '0%';
    }
  }
}
