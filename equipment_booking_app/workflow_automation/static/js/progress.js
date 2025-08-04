document.addEventListener('DOMContentLoaded', function () {
  const container = document.getElementById('zip-progress-container');
  if (!container) return;
  const bar = document.getElementById('zip-progress-bar');
  const percent = document.getElementById('zip-progress-percent');
  const taskName = document.getElementById('zip-task-name');
  const inputEl = document.getElementById('zip-input-path');
  const outputEl = document.getElementById('zip-output-path');
  const doneList = document.getElementById('zip-files-completed');
  const pendingList = document.getElementById('zip-files-pending');
  
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  function sendAction(action) {
    fetch('/progress-control/', {
      method: 'POST',
      headers: {'X-CSRFToken': csrftoken},
      body: new URLSearchParams({action})
    });
  }

  document.getElementById('pause-btn').addEventListener('click', () => sendAction('pause'));
  document.getElementById('resume-btn').addEventListener('click', () => sendAction('resume'));
  document.getElementById('cancel-btn').addEventListener('click', () => sendAction('cancel'));
  document.getElementById('restart-btn').addEventListener('click', () => sendAction('restart'));

  function update() {
    fetch('/progress-status/')
      .then(r => r.json())
      .then(data => {
        if (data.status && data.status !== 'idle') {
          container.style.display = 'block';
          taskName.textContent = data.task || 'Zipping RCP Files';
          bar.style.width = data.percent + '%';
          percent.textContent = data.percent + '%';
          inputEl.textContent = data.input_path || '';
          outputEl.textContent = data.output_path || '';

          doneList.innerHTML = '';
          (data.completed_files || []).forEach(f => {
            const li = document.createElement('li');
            li.textContent = f;
            doneList.appendChild(li);
          });

          pendingList.innerHTML = '';
          (data.pending_files || []).forEach(f => {
            const li = document.createElement('li');
            li.textContent = f;
            pendingList.appendChild(li);
          });
        } else {
          container.style.display = 'none';
        }
      });
  }

  update();
  setInterval(update, 3000);
});
