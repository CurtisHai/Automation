document.addEventListener('DOMContentLoaded', function () {
  const demoBtn = document.getElementById('demo-btn');
  if (!demoBtn) return;

  const container = document.getElementById('demo-container');
  const bar = document.getElementById('demo-progress-bar');
  const action = document.getElementById('demo-current-action');
  const logList = document.getElementById('demo-log');
  const complete = document.getElementById('demo-complete');

  demoBtn.addEventListener('click', () => {
    container.classList.remove('d-none');
    bar.classList.remove('bg-success');
    bar.style.width = '0%';
    bar.textContent = '0%';
    action.textContent = '';
    logList.innerHTML = '';
    complete.classList.add('d-none');

    const steps = [
      { time: 0, text: 'Starting demo workflow...' },
      { time: 10, text: 'Reading input files...' },
      { time: 20, text: 'Processing data...' },
      { time: 40, text: 'Finalising...' },
      { time: 60, text: 'Demo complete.' }
    ];

    let stepIndex = 0;
    const total = 60; // seconds
    let elapsed = 0;

    const timer = setInterval(() => {
      elapsed++;
      const percent = Math.min(100, Math.floor((elapsed / total) * 100));
      bar.style.width = percent + '%';
      bar.textContent = percent + '%';

      if (stepIndex < steps.length && elapsed >= steps[stepIndex].time) {
        const msg = steps[stepIndex].text;
        action.textContent = msg;
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.textContent = msg;
        logList.appendChild(li);
        stepIndex++;
      }

      if (elapsed >= total) {
        clearInterval(timer);
        bar.classList.add('bg-success');
        complete.classList.remove('d-none');
      }
    }, 1000);
  });
});

