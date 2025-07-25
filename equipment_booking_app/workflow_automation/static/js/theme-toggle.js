document.addEventListener('DOMContentLoaded', function () {
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  const body = document.body;
  const saved = localStorage.getItem('theme');
  if (saved) {
    body.classList.remove('dark-mode', 'light-mode');
    body.classList.add(saved);
  }
  toggle.addEventListener('click', function () {
    body.classList.toggle('light-mode');
    body.classList.toggle('dark-mode');
    const mode = body.classList.contains('light-mode') ? 'light-mode' : 'dark-mode';
    localStorage.setItem('theme', mode);
  });
});
