const form = document.querySelector('#contact-form');
form?.addEventListener('submit', async event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const button = form.querySelector('button[type="submit"]');
  const status = document.querySelector('#contact-status');
  const original = button.innerHTML;
  button.disabled = true; button.textContent = 'Sending…'; status.className = 'form-status'; status.textContent = '';
  try {
    const response = await fetch(form.action, { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))), headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.csrf_token.value}, credentials: 'same-origin' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || 'Unable to send. Please try again.');
    status.textContent = data.message; status.classList.add('success'); form.reset();
  } catch (error) { status.textContent = error.message || 'Network error. Please try again.'; status.classList.add('error'); }
  finally { button.disabled = false; button.innerHTML = original; }
});
