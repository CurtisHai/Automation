document.addEventListener('DOMContentLoaded', function () {
  const bar = document.getElementById('wf-progress-bar');
  const action = document.getElementById('wf-current-action');
  const logList = document.getElementById('wf-log');
  const errorBox = document.getElementById('wf-error');
  const completeBox = document.getElementById('wf-complete');

  function update() {
    fetch(`/workflows/status/${RUN_ID}/`)
      .then(r => r.json())
      .then(data => {
        bar.style.width = data.percent + '%';
        bar.textContent = data.percent + '%';
        action.textContent = data.current_action || '';

        logList.innerHTML = '';
        (data.logs || []).forEach(line => {
          const li = document.createElement('li');
          li.className = 'list-group-item';
          li.textContent = line;
          logList.appendChild(li);
        });

        if (data.status === 'completed') {
          bar.classList.add('bg-success');
          completeBox.classList.remove('d-none');
        } else if (data.status === 'error') {
          bar.classList.add('bg-danger');
          errorBox.textContent = data.error || 'Error';
          errorBox.classList.remove('d-none');
        }
      });
  }

  update();
  setInterval(update, 1000);
});
