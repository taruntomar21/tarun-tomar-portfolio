document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => { if (!window.confirm(form.dataset.confirm)) event.preventDefault(); });
});
const previewUrls = new Map();
document.querySelectorAll('input[data-preview]').forEach(input => {
  input.addEventListener('change', () => {
    (previewUrls.get(input) || []).forEach(URL.revokeObjectURL);
    const container = document.getElementById(input.dataset.preview); container.replaceChildren();
    const urls = [];
    for (const file of input.files) {
      if (!['image/jpeg','image/png','image/webp'].includes(file.type)) continue;
      const img = document.createElement('img'); const url = URL.createObjectURL(file); urls.push(url);
      img.src = url; img.alt = `Preview of ${file.name}`; container.append(img);
    }
    previewUrls.set(input, urls);
  });
});
const imageIds = document.querySelector('#remove-image-ids');
if (imageIds) document.querySelectorAll('.remove-image').forEach(box => box.addEventListener('change', () => {
  imageIds.value = [...document.querySelectorAll('.remove-image:checked')].map(el => el.value).join(',');
}));
const title = document.querySelector('#title'); const slug = document.querySelector('#slug');
let manuallyEdited = Boolean(slug?.value);
slug?.addEventListener('input', () => { manuallyEdited = true; });
title?.addEventListener('input', () => {
  if (!slug || manuallyEdited) return;
  slug.value = title.value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0,200).replace(/-$/,'');
});
