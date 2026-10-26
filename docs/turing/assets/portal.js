/* Audience-filtered index only. Never fetch the source manifest or restricted docs. */
const script = document.currentScript;
const base = new URL('.', script.src);
const menu = document.getElementById('menu');
const nav = document.getElementById('navigation');
nav.dataset.collapsed = 'true';
menu.addEventListener('click', () => {
  const expanded = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(expanded));
  nav.dataset.collapsed = String(!expanded);
});
let index;
const input = document.getElementById('search');
const results = document.getElementById('search-results');
const status = document.getElementById('search-status');
let serial = 0;
input.addEventListener('input', async () => {
  const request = ++serial;
  const terms = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  results.replaceChildren(); status.textContent = '';
  if (!terms.length) return;
  try {
    if (!index) {
      const response = await fetch(new URL('search-index.json', base));
      if (!response.ok) throw new Error('search unavailable');
      index = await response.json();
    }
    if (request !== serial) return;
    const matches = index.filter(row => terms.every(term => (row.title + ' ' + row.text).toLowerCase().includes(term)));
    status.textContent = matches.length ? `${matches.length} matching pages` : 'No matches. Try a concept or interface name.';
    matches.slice(0, 20).forEach(row => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = new URL(row.url, base); a.textContent = row.title;
      li.append(a); results.append(li);
    });
  } catch (_) { if (request === serial) status.textContent = 'Search unavailable. Use the documentation navigation.'; }
});
document.querySelectorAll('pre > code').forEach(code => {
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'copy'; button.textContent = 'Copy';
  button.setAttribute('aria-label', 'Copy code or equation block');
  button.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(code.textContent); button.textContent = 'Copied'; }
    catch (_) { button.textContent = 'Select text to copy'; }
    setTimeout(() => { button.textContent = 'Copy'; }, 2000);
  });
  code.parentElement.before(button);
});
