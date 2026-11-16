function updateSummary() {
  const items = document.querySelectorAll('[data-status]');
  const completed = document.querySelectorAll('[data-status="done"]');
  document.getElementById('summary').textContent = `共 ${items.length} 项，已完成 ${completed.length} 项`;
}

updateSummary();
