const $ = selector => document.querySelector(selector);
const browserButtons = [...document.querySelectorAll('[data-browser]')];
let token = '';
let terminalBusy = false, browserBusy = false, pageOpen = false;

try {
  if (localStorage.getItem('codelaboon.theme') === 'light') document.body.classList.add('light');
} catch {}

function controls() {
  $('#open-terminal').disabled = $('#run-command').disabled = !token || terminalBusy;
  for (const button of browserButtons) {
    button.disabled = !token || browserBusy ||
      (!pageOpen && !['navigate', 'close'].includes(button.dataset.browser));
  }
}

async function desktop(action, arguments_) {
  const response = await fetch('/api/desktop', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Codelaboon-Token': token},
    body: JSON.stringify({action, ...arguments_})
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Desktop request failed.');
  return data;
}

async function terminal(action, argv) {
  terminalBusy = true;
  controls();
  const status = $('#terminal-status'), output = $('#command-output');
  status.textContent = action === 'command' ? 'Running command…' : 'Opening terminal…';
  if (action === 'command') output.hidden = true;
  try {
    const data = await desktop(action, {argv});
    status.textContent = data.message || ('Exit code ' + data.exit_code + (data.truncated ? ' · showing the last 16 KB' : ''));
    if (action === 'command') {
      output.textContent = data.output || 'No output';
      output.hidden = false;
    }
  } catch (error) {
    status.textContent = error.message;
  } finally {
    terminalBusy = false;
    controls();
  }
}

async function browser(action) {
  browserBusy = true;
  controls();
  const status = $('#browser-status'), output = $('#browser-output');
  status.textContent = 'Waiting for Chromium…';
  try {
    const data = await desktop(action, {
      url: $('#browser-url').value, selector: $('#browser-selector').value, text: $('#browser-text').value
    });
    pageOpen = action !== 'close';
    status.textContent = data.message || data.title + ' · ' + data.url;
    output.hidden = !pageOpen;
    output.textContent = data.snapshot || '';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    browserBusy = false;
    controls();
  }
}

$('#open-terminal').onclick = () => terminal('terminal');
$('#command-form').onsubmit = event => {
  event.preventDefault();
  if (terminalBusy) return;
  try {
    terminal('command', JSON.parse($('#command').value));
  } catch {
    $('#terminal-status').textContent = 'Enter a JSON array such as ["git", "status"].';
  }
};
$('#navigate-form').onsubmit = event => {
  event.preventDefault();
  if (!browserBusy) browser('navigate');
};
$('#browser-controls').onsubmit = event => event.preventDefault();
for (const button of browserButtons.filter(button => button.type === 'button')) {
  button.onclick = () => browser(button.dataset.browser);
}

(async () => {
  try {
    const response = await fetch('/api/session');
    if (!response.ok) throw Error('Reload this page from the printed workspace URL.');
    const session = await response.json();
    token = session.token;
    $('#desktop-workspace').textContent = session.workspace + ' · ' + session.platform;
    controls();
  } catch (error) {
    $('#desktop-workspace').textContent = error.message;
  }
})();
