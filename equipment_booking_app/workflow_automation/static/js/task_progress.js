document.addEventListener('DOMContentLoaded', function () {
  const container = document.getElementById('task-progress-container');
  if (!container) return;
  const bar = document.getElementById('task-progress-bar');
  const current = document.getElementById('task-current');

  function update() {
    fetch('/progress-status/')
      .then(r => r.json())
      .then(data => {
        if (data.status && data.status !== 'idle') {
          container.classList.remove('d-none');
          bar.style.width = data.percent + '%';
          bar.textContent = data.percent + '%';
          current.textContent = data.current_file || '';
          if (data.status === 'done') {
            bar.classList.add('bg-success');
          } else if (data.status === 'cancelled') {
            bar.classList.add('bg-danger');
          }
        } else {
          container.classList.add('d-none');
          bar.classList.remove('bg-success', 'bg-danger');
          bar.style.width = '0%';
          bar.textContent = '0%';
          current.textContent = '';
        }
      });
  }

  update();
  setInterval(update, 1000);
});
