import { refreshIcons } from './main.js';
// Progressive enhancement: the same GET form and pagination work without JavaScript.
const form = document.querySelector('#project-filters');
let currentRequest;
form?.addEventListener('submit', async event => {
  event.preventDefault();
  currentRequest?.abort(); currentRequest = new AbortController();
  const params = new URLSearchParams(new FormData(form));
  for (const [key, value] of [...params]) if (!value) params.delete(key);
  const url = `/projects?${params}`;
  const results = document.querySelector('#project-results');
  const count = document.querySelector('#project-count');
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true; button.textContent = 'Loading…'; results.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(url, { signal: currentRequest.signal });
    if (!response.ok) throw new Error('Could not load projects. Please try again.');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    // Server-rendered, autoescaped, same-origin fragments only; no user HTML injection.
    const next = doc.querySelector('#project-results');
    if (!next) throw new Error('Unexpected response. Reload to try again.');
    results.replaceChildren(...Array.from(next.childNodes));
    count.textContent = doc.querySelector('#project-count').textContent;
    history.pushState(null, '', url); refreshIcons();
  } catch (error) {
    if (error.name !== 'AbortError') count.textContent = error.message;
  } finally { button.disabled = false; button.textContent = 'Apply'; results.removeAttribute('aria-busy'); }
});
window.addEventListener('popstate', () => location.reload());
