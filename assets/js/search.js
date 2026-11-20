// Static keyword search over the pagefind index (/pagefind/pagefind.js),
// built from the item pages in the container image. Results render as the same
// title/thumbnail cards the browse pages use, paged with a "show more" button.

const PAGE_SIZE = 50;

const scriptEl = document.querySelector('script[data-strings]'); // currentScript is null in module scripts
let STR = {
  searching: 'Searching…',
  results: 'results',
  noresults: 'No results',
  showmore: 'Show more',
  unavailable: 'Search is unavailable on this build.',
};
try {
  STR = Object.assign(STR, JSON.parse(scriptEl.getAttribute('data-strings') || '{}'));
} catch (e) { /* keep defaults */ }

const form = document.getElementById('search-page-form');
const input = document.getElementById('search-input');
const statusEl = document.getElementById('search-status');
const resultsEl = document.getElementById('items-primary');
const moreEl = document.getElementById('search-more');

let pagefind = null;
let results = [];
let shown = 0;

async function ensurePagefind() {
  if (!pagefind) {
    pagefind = await import('/pagefind/pagefind.js');
    await pagefind.options({ excerptLength: 25 });
  }
  return pagefind;
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function cardHTML(d) {
  // Title-only row, matching the browse list (the original search results are a
  // title list too; no thumbnails — which also avoids broken /files/ images).
  const url = d.url || '#';
  const title = (d.meta && d.meta.title) || d.url || 'Untitled';
  return (
    '<div class="item record hentry"><h2><a href="' +
    escapeHtml(url) + '" class="permalink">' + escapeHtml(title) + '</a></h2></div>'
  );
}

function updateMore() {
  moreEl.innerHTML = '';
  const remaining = results.length - shown;
  if (remaining > 0) {
    const b = document.createElement('button');
    b.type = 'button';
    b.id = 'show-more';
    b.textContent = STR.showmore + ' (' + remaining + ')';
    b.addEventListener('click', renderMore);
    moreEl.appendChild(b);
  }
}

async function renderMore() {
  const slice = results.slice(shown, shown + PAGE_SIZE);
  const datas = await Promise.all(slice.map((r) => r.data()));
  resultsEl.insertAdjacentHTML('beforeend', datas.map(cardHTML).join(''));
  shown += slice.length;
  updateMore();
}

async function doSearch(q) {
  resultsEl.innerHTML = '';
  moreEl.innerHTML = '';
  results = [];
  shown = 0;
  q = (q || '').trim();
  if (!q) { statusEl.textContent = ''; return; }
  statusEl.textContent = STR.searching;
  let pf;
  try { pf = await ensurePagefind(); }
  catch (e) { statusEl.textContent = STR.unavailable; return; }
  const search = await pf.search(q);
  results = search.results;
  const n = results.length;
  statusEl.textContent = n === 0 ? STR.noresults : (n + ' ' + STR.results + ' — “' + q + '”');
  await renderMore();
}

function syncURL(q) {
  const url = new URL(window.location);
  if (q) url.searchParams.set('q', q); else url.searchParams.delete('q');
  window.history.replaceState(null, '', url);
}

if (form) {
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    syncURL(input.value.trim());
    doSearch(input.value);
  });
}

const params = new URLSearchParams(window.location.search);
const q0 = params.get('q') || '';
if (input) input.value = q0;
if (q0) doSearch(q0);
