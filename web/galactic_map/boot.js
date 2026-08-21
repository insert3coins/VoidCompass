const loading = document.getElementById('loading-status');
window.addEventListener('error', (event) => {
  if (loading) loading.textContent = `Atlas script error: ${event.message || 'unknown error'}`;
});
window.addEventListener('unhandledrejection', (event) => {
  if (loading) loading.textContent = `Atlas startup error: ${event.reason?.message || event.reason || 'unknown error'}`;
});
import('/app.js').catch((error) => {
  console.error(error);
  if (loading) loading.textContent = `Atlas module unavailable: ${error.message || error}`;
});
