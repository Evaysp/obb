// Cookie-Bridge popup logic.
//
// For each known paywall source, read every cookie scoped to its root domain
// via chrome.cookies.getAll (this includes HttpOnly cookies, which page-side
// JS can never see) and POST them to the Observer backend.

const SOURCES = [
  { slug: 'nikkei',    name: 'Nikkei',           domain: 'nikkei.com' },
  { slug: 'ft',        name: 'Financial Times',  domain: 'ft.com' },
  { slug: 'bloomberg', name: 'Bloomberg',        domain: 'bloomberg.com' },
  { slug: 'economist', name: 'The Economist',    domain: 'economist.com' },
  { slug: 'scmp',      name: 'SCMP',             domain: 'scmp.com' },
  { slug: 'caixin',    name: 'Caixin',           domain: 'caixin.com' },
];

const $sources = document.getElementById('sources');
const $endpoint = document.getElementById('endpoint');
const $status = document.getElementById('status');

const DEFAULT_ENDPOINT = 'http://localhost:4433';

// Load saved endpoint
chrome.storage.local.get({ endpoint: DEFAULT_ENDPOINT }, ({ endpoint }) => {
  $endpoint.value = endpoint;
});
$endpoint.addEventListener('change', () => {
  const v = $endpoint.value.trim().replace(/\/+$/, '') || DEFAULT_ENDPOINT;
  chrome.storage.local.set({ endpoint: v });
  $endpoint.value = v;
});

// Render rows
for (const src of SOURCES) {
  const row = document.createElement('div');
  row.className = 'src';

  const meta = document.createElement('div');
  meta.innerHTML = `<div class="name">${src.name}</div><div class="meta">${src.domain}</div>`;

  const btn = document.createElement('button');
  btn.textContent = '▸ send';
  btn.addEventListener('click', () => sendCookies(src, btn));

  row.appendChild(meta);
  row.appendChild(btn);
  $sources.appendChild(row);
}

function setStatus(text, kind = '') {
  $status.textContent = text;
  $status.className = 'status' + (kind ? ' ' + kind : '');
}

async function sendCookies(src, btn) {
  btn.disabled = true;
  setStatus(`reading ${src.domain} cookies…`);
  try {
    // .getAll({domain}) returns cookies whose Domain attribute matches that
    // SLD or any subdomain. Includes HttpOnly cookies — that's the whole point.
    const raw = await new Promise((resolve, reject) => {
      chrome.cookies.getAll({ domain: src.domain }, (cookies) => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(cookies);
      });
    });

    if (!raw || raw.length === 0) {
      setStatus(`no cookies for ${src.domain}. log in to ${src.name} in a normal tab first.`, 'warn');
      return;
    }

    const formatted = raw.map(c => ({
      name: c.name,
      value: c.value,
      domain: c.domain,
      path: c.path,
      secure: c.secure,
      httpOnly: c.httpOnly,
      ...(typeof c.expirationDate === 'number' ? { expirationDate: c.expirationDate } : {}),
    }));

    const endpoint = $endpoint.value.trim().replace(/\/+$/, '') || DEFAULT_ENDPOINT;
    const url = `${endpoint}/api/sources/${src.slug}/cookies`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cookies: formatted,
        userAgent: navigator.userAgent,
      }),
    });
    let body = null;
    try { body = await resp.json(); } catch { /* ignore */ }

    if (!resp.ok) {
      const msg = body?.error?.message || body?.message || `HTTP ${resp.status}`;
      setStatus(`${resp.status}: ${msg}`, 'err');
      return;
    }

    if (body && body.ok === false) {
      setStatus(`${body.error || 'failed'}: ${body.message || ''}`, 'err');
      return;
    }

    const expiresPart = body?.expiresAt
      ? ` · expires ${new Date(body.expiresAt).toLocaleDateString()}`
      : '';
    setStatus(`✓ saved ${formatted.length} ${src.name} cookies${expiresPart}`, 'ok');
  } catch (e) {
    setStatus(`! ${e.message || e}`, 'err');
  } finally {
    btn.disabled = false;
  }
}
