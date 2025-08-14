document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.js-data-table tbody tr[data-href]').forEach(row => {
    row.addEventListener('click', () => {
      window.location.href = row.dataset.href;
    });
  });
});
