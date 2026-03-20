// PyStack Web UI -- connects the three panels to the API.

// -- Tab switching --
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.panel).classList.add('active');

        // Focus the right input.
        const panel = tab.dataset.panel;
        if (panel === 'terminal') document.getElementById('terminal-input').focus();
        if (panel === 'sql') document.getElementById('sql-input').focus();
    });
});

// -- Helpers --
function appendOutput(elementId, text, className) {
    const el = document.getElementById(elementId);
    const line = document.createElement('div');
    line.textContent = text;
    if (className) line.className = className;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
}

async function postJSON(url, body) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return resp.json();
}

// -- Terminal --
const terminalInput = document.getElementById('terminal-input');
const terminalHistory = [];
let historyIndex = -1;

terminalInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        const cmd = terminalInput.value.trim();
        if (!cmd) return;
        terminalHistory.push(cmd);
        historyIndex = terminalHistory.length;
        appendOutput('terminal-output', `pystack-os> ${cmd}`);
        terminalInput.value = '';

        const data = await postJSON('/api/shell', { command: cmd });
        if (data.output) {
            appendOutput('terminal-output', data.output);
        }
        if (data.halted) {
            appendOutput('terminal-output', '[System halted]', 'error');
            terminalInput.disabled = true;
        }
    }
    if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (historyIndex > 0) {
            historyIndex--;
            terminalInput.value = terminalHistory[historyIndex];
        }
    }
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (historyIndex < terminalHistory.length - 1) {
            historyIndex++;
            terminalInput.value = terminalHistory[historyIndex];
        } else {
            historyIndex = terminalHistory.length;
            terminalInput.value = '';
        }
    }
});

// -- Pebble Editor --
document.getElementById('pebble-run').addEventListener('click', async () => {
    const source = document.getElementById('pebble-source').value;
    const output = document.getElementById('pebble-output');
    output.textContent = 'Running...\n';

    const data = await postJSON('/api/pebble', { source });
    output.textContent = data.output || '(no output)';
    if (data.error) output.classList.add('error');
    else output.classList.remove('error');
});

// -- SQL Console --
const sqlInput = document.getElementById('sql-input');

sqlInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        const sql = sqlInput.value.trim();
        if (!sql) return;
        appendOutput('sql-output', `sql> ${sql}`);
        sqlInput.value = '';

        const data = await postJSON('/api/sql', { sql });
        const cls = data.error ? 'error' : '';
        appendOutput('sql-output', data.output || '(no output)', cls);
    }
});
