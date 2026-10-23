export function refreshIcons() { window.lucide?.createIcons(); }
refreshIcons();
const menu = document.querySelector('#primary-nav');
const toggle = document.querySelector('#menu-toggle');
function closeMenu() { menu?.classList.remove('is-open'); toggle?.setAttribute('aria-expanded', 'false'); toggle?.setAttribute('aria-label', 'Open navigation'); }
toggle?.addEventListener('click', () => {
  const open = menu.classList.toggle('is-open');
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && menu?.classList.contains('is-open')) { closeMenu(); toggle.focus(); } });
document.addEventListener('click', e => { if (!e.target.closest('.site-header')) closeMenu(); });
menu?.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
matchMedia('(min-width: 961px)').addEventListener('change', e => { if (e.matches) closeMenu(); });
const year = document.querySelector('#copyright-year'); if (year) year.textContent = new Date().getFullYear();
