(() => {
  let preference;
  try { preference = localStorage.getItem('portfolio-theme'); } catch (_) {}
  const media = matchMedia('(prefers-color-scheme: dark)');
  document.documentElement.dataset.theme = preference === 'light' || preference === 'dark' ? preference : media.matches ? 'dark' : 'light';
  media.addEventListener('change', event => {
    let saved;
    try { saved = localStorage.getItem('portfolio-theme'); } catch (_) {}
    if (!saved) document.documentElement.dataset.theme = event.matches ? 'dark' : 'light';
  });
  document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('#theme-toggle');
    const updateLabel = () => { if (button) button.setAttribute('aria-label', `Switch to ${document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'} theme`); };
    updateLabel();
    button?.addEventListener('click', () => {
      const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = theme;
      try { localStorage.setItem('portfolio-theme', theme); } catch (_) {}
      updateLabel();
    });
  });
})();
