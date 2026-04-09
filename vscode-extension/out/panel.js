"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.TicketAgentPanel = void 0;
/**
 * Sidebar webview panel.
 *
 * Network calls happen in the extension host (Node.js) via http/https module.
 * The webview handles all UI — letter avatars, @mention autocomplete, ticket cards.
 */
const vscode = __importStar(require("vscode"));
const https = __importStar(require("https"));
const http = __importStar(require("http"));
const config_1 = require("./config");
class TicketAgentPanel {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = this._getHtml();
        // Init: connector status + load members
        this._loadStatus();
        this._loadMembers();
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.command) {
                case 'createTicket':
                    await this._createTicket(msg.text);
                    break;
                case 'listTickets':
                    await this._listTickets();
                    break;
                case 'openUrl':
                    vscode.env.openExternal(vscode.Uri.parse(msg.url));
                    break;
            }
        });
    }
    async prefillFromSelection(text) {
        this._view?.webview.postMessage({ command: 'prefill', text });
    }
    // ── HTTP (extension host / Node.js) ───────────────────────────────────────
    _request(path, method = 'GET', body) {
        return new Promise((resolve, reject) => {
            const url = new URL(path, (0, config_1.getConfig)().backendUrl);
            const lib = url.protocol === 'https:' ? https : http;
            const payload = body ? JSON.stringify(body) : undefined;
            const req = lib.request({
                hostname: url.hostname,
                port: url.port || (url.protocol === 'https:' ? 443 : 80),
                path: url.pathname + url.search,
                method,
                headers: {
                    'Accept': 'application/json',
                    ...(payload ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } : {}),
                },
            }, (res) => {
                let data = '';
                res.on('data', c => data += c);
                res.on('end', () => { try {
                    resolve(JSON.parse(data));
                }
                catch {
                    resolve(data);
                } });
            });
            req.on('error', reject);
            if (payload) {
                req.write(payload);
            }
            req.end();
        });
    }
    async _loadStatus() {
        try {
            const d = await this._request('/status');
            this._post({
                command: 'connectorStatus',
                connected: d?.connected ?? false,
                displayName: d?.display_name ?? 'Unknown',
                color: d?.color ?? '#888',
                project: d?.project ?? '',
            });
        }
        catch {
            this._post({ command: 'connectorStatus', connected: false, displayName: 'Offline', color: '#888', project: '' });
        }
    }
    async _loadMembers() {
        try {
            const d = await this._request('/chat/members');
            const members = d?.members ?? [];
            this._post({ command: 'membersLoaded', members });
        }
        catch { /* silently fail — autocomplete just won't show */ }
    }
    async _createTicket(text) {
        this._post({ command: 'thinking' });
        try {
            const result = await this._request('/chat', 'POST', { message: text });
            this._post({ command: 'ticketCreated', result });
        }
        catch (e) {
            this._post({ command: 'ticketCreated', result: { success: false, message: 'Could not reach backend: ' + e.message } });
        }
    }
    async _listTickets() {
        try {
            const tickets = await this._request('/tickets?limit=8');
            this._post({ command: 'ticketList', tickets: Array.isArray(tickets) ? tickets : [] });
        }
        catch (e) {
            this._post({ command: 'error', message: 'Could not fetch tickets: ' + e.message });
        }
    }
    _post(msg) { this._view?.webview.postMessage(msg); }
    // ── HTML ──────────────────────────────────────────────────────────────────
    _getHtml() {
        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ticket Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-foreground);
    background: var(--vscode-sideBar-background);
    padding: 12px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
  }
  /* Platform badge */
  .platform-bar {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; border-radius: 6px;
    background: var(--vscode-badge-background);
    font-size: 12px; font-weight: 600;
  }
  .platform-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }
  .platform-name { flex: 1; }
  .platform-project { font-size: 10px; font-weight: 400; opacity: 0.75; }

  /* Input area */
  .input-wrap { position: relative; }
  textarea {
    width: 100%;
    min-height: 72px;
    padding: 8px;
    border: 1px solid var(--vscode-input-border);
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border-radius: 4px;
    resize: vertical;
    font-family: inherit;
    font-size: inherit;
  }
  textarea:focus { outline: 1px solid var(--vscode-focusBorder); }

  /* @mention dropdown */
  #mention-dropdown {
    display: none;
    position: absolute;
    bottom: calc(100% + 4px);
    left: 0; right: 0;
    background: var(--vscode-dropdown-background);
    border: 1px solid var(--vscode-dropdown-border);
    border-radius: 4px;
    max-height: 160px;
    overflow-y: auto;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  #mention-dropdown.open { display: block; }
  .mention-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 12px;
  }
  .mention-item:hover, .mention-item.active {
    background: var(--vscode-list-hoverBackground);
  }

  /* Buttons */
  button {
    width: 100%;
    padding: 6px 12px;
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: inherit;
  }
  button:hover { background: var(--vscode-button-hoverBackground); }
  button.secondary {
    background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground);
    margin-top: 4px;
  }

  /* Output feed */
  #output {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .msg { padding: 8px 10px; border-radius: 6px; font-size: 12px; line-height: 1.5; }
  .msg.user    { background: var(--vscode-inputOption-activeBackground); }
  .msg.agent   { background: var(--vscode-diffEditor-insertedLineBackground); }
  .msg.error   { background: var(--vscode-inputValidation-errorBackground); font-size: 11px; }
  .msg.loading { opacity: 0.6; font-style: italic; font-size: 11px; }

  /* Ticket card */
  .ticket-card { display: flex; flex-direction: column; gap: 6px; }
  .ticket-card-header { display: flex; align-items: center; gap: 8px; }
  .avatar {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: #fff;
    flex-shrink: 0;
  }
  .ticket-assignee { font-size: 11px; color: var(--vscode-descriptionForeground); }
  .ticket-id { font-size: 10px; color: var(--vscode-descriptionForeground); }
  .ticket-title { font-weight: 600; font-size: 13px; }
  .ticket-meta { display: flex; gap: 6px; flex-wrap: wrap; }
  .badge {
    font-size: 10px; padding: 2px 7px; border-radius: 10px;
    background: var(--vscode-badge-background);
    color: var(--vscode-badge-foreground);
    text-transform: capitalize;
  }
  .ticket-link {
    font-size: 11px; color: var(--vscode-textLink-foreground);
    cursor: pointer; text-decoration: underline; display: inline-block;
  }

  /* Ticket list rows */
  .list-header { font-size: 11px; font-weight: 600; color: var(--vscode-descriptionForeground); margin-bottom: 4px; }
  .ticket-row {
    display: flex; align-items: center; gap: 8px;
    padding: 5px 4px; border-radius: 4px; cursor: pointer;
  }
  .ticket-row:hover { background: var(--vscode-list-hoverBackground); }
  .ticket-id-sm { font-size: 10px; color: var(--vscode-descriptionForeground); min-width: 28px; }
  .ticket-title-sm { flex: 1; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .badge-sm {
    font-size: 10px; padding: 1px 5px; border-radius: 8px;
    background: var(--vscode-badge-background);
    color: var(--vscode-badge-foreground); white-space: nowrap;
  }
</style>
</head>
<body>

<div class="platform-bar" id="platform-bar">
  <div class="platform-dot" id="platform-dot" style="background:#888"></div>
  <span class="platform-name" id="platform-name">Connecting...</span>
  <span class="platform-project" id="platform-project"></span>
</div>

<div class="input-wrap">
  <div id="mention-dropdown"></div>
  <textarea id="input" placeholder="Describe the ticket... (type @ to mention someone)"></textarea>
</div>

<button id="btn-create">Create Ticket</button>
<button id="btn-list" class="secondary">Recent Tickets</button>
<div id="output"></div>

<script>
  const vscode      = acquireVsCodeApi();
  const output      = document.getElementById('output');
  const input       = document.getElementById('input');
  const platformDot = document.getElementById('platform-dot');
  const platformName = document.getElementById('platform-name');
  const platformProject = document.getElementById('platform-project');
  const dropdown    = document.getElementById('mention-dropdown');

  let members = [];
  let mentionStart = -1;
  let activeIdx = 0;

  // ── Helpers ────────────────────────────────────────────────────────────────

  function esc(t) {
    return String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function avatarColor(name) {
    const colors = ['#e05c5c','#e08a3c','#d4a62a','#5cb85c','#3c9ae0','#7c5cbf','#d45c8a','#3ca0a0'];
    let h = 0;
    for (let i = 0; i < name.length; i++) { h = name.charCodeAt(i) + ((h << 5) - h); }
    return colors[Math.abs(h) % colors.length];
  }

  function initials(name) {
    return (name || '?').split(/\\s+/).map(w => w[0]).join('').toUpperCase().slice(0,2);
  }

  function avatarHtml(name) {
    return '<div class="avatar" style="background:' + avatarColor(name) + '">' + esc(initials(name)) + '</div>';
  }

  function addMsg(html, type) {
    const div = document.createElement('div');
    div.className = 'msg ' + type;
    div.innerHTML = html;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
    return div;
  }

  // ── @mention autocomplete ─────────────────────────────────────────────────

  function showMentions(query) {
    const matches = members.filter(m =>
      m.displayName.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 8);

    if (!matches.length) { hideMentions(); return; }

    activeIdx = 0;
    dropdown.innerHTML = matches.map((m, i) =>
      '<div class="mention-item' + (i === 0 ? ' active' : '') + '" data-name="' + esc(m.displayName) + '">' +
        avatarHtml(m.displayName) +
        '<span>' + esc(m.displayName) + '</span>' +
      '</div>'
    ).join('');
    dropdown.classList.add('open');
  }

  function hideMentions() {
    dropdown.classList.remove('open');
    mentionStart = -1;
  }

  function insertMention(name) {
    const val = input.value;
    const before = val.slice(0, mentionStart);
    const after  = val.slice(input.selectionStart);
    input.value = before + '@' + name + ' ' + after;
    input.selectionStart = input.selectionEnd = mentionStart + name.length + 2;
    hideMentions();
    input.focus();
  }

  input.addEventListener('input', () => {
    const pos = input.selectionStart;
    const text = input.value.slice(0, pos);
    const atIdx = text.lastIndexOf('@');
    if (atIdx === -1 || (atIdx > 0 && !/\\s/.test(text[atIdx - 1]))) { hideMentions(); return; }
    const query = text.slice(atIdx + 1);
    if (/\\s/.test(query)) { hideMentions(); return; }
    mentionStart = atIdx;
    showMentions(query);
  });

  input.addEventListener('keydown', e => {
    if (dropdown.classList.contains('open')) {
      const items = dropdown.querySelectorAll('.mention-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        items[activeIdx]?.classList.remove('active');
        activeIdx = (activeIdx + 1) % items.length;
        items[activeIdx]?.classList.add('active');
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        items[activeIdx]?.classList.remove('active');
        activeIdx = (activeIdx - 1 + items.length) % items.length;
        items[activeIdx]?.classList.add('active');
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const name = items[activeIdx]?.dataset?.name;
        if (name) { insertMention(name); }
      } else if (e.key === 'Escape') {
        hideMentions();
      }
      return;
    }
    // Cmd/Ctrl+Enter submits
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      document.getElementById('btn-create').click();
    }
  });

  dropdown.addEventListener('click', e => {
    const item = e.target.closest('.mention-item');
    if (item?.dataset?.name) { insertMention(item.dataset.name); }
  });

  // ── Ticket actions ────────────────────────────────────────────────────────

  document.getElementById('btn-create').addEventListener('click', () => {
    const text = input.value.trim();
    if (!text) return;
    addMsg(esc(text), 'user');
    input.value = '';
    vscode.postMessage({ command: 'createTicket', text });
  });

  document.getElementById('btn-list').addEventListener('click', () => {
    vscode.postMessage({ command: 'listTickets' });
  });

  // Click delegation — ticket links and rows
  document.addEventListener('click', e => {
    const link = e.target.closest('.ticket-link');
    const row  = e.target.closest('.ticket-row');
    const url  = (link || row)?.dataset?.url;
    if (url) { vscode.postMessage({ command: 'openUrl', url }); }
  });

  // ── Messages from extension host ──────────────────────────────────────────

  window.addEventListener('message', e => {
    const msg = e.data;
    switch (msg.command) {

      case 'connectorStatus':
        platformDot.style.background = msg.connected ? msg.color : '#888';
        platformName.textContent = msg.connected ? msg.displayName : msg.displayName + ' — offline';
        platformProject.textContent = msg.project ? '· ' + msg.project : '';
        break;

      case 'membersLoaded':
        members = msg.members || [];
        break;

      case 'thinking':
        addMsg('Creating ticket...', 'loading');
        break;

      case 'ticketCreated': {
        const loading = output.querySelector('.loading');
        if (loading) { loading.remove(); }
        const r = msg.result;
        if (r.success && r.target_ticket) {
          const t = r.result || r.target_ticket;
          const assignee = r.parsed?.assignee || 'Unassigned';
          const html =
            '<div class="ticket-card">' +
              '<div class="ticket-card-header">' +
                avatarHtml(assignee) +
                '<div>' +
                  '<div class="ticket-id">#' + esc(t.id || r.target_ticket?.id) + '</div>' +
                  '<div class="ticket-assignee">' + esc(assignee) + '</div>' +
                '</div>' +
              '</div>' +
              '<div class="ticket-title">' + esc(r.parsed?.title || '') + '</div>' +
              '<div class="ticket-meta">' +
                '<span class="badge">' + esc(r.parsed?.priority || '') + '</span>' +
                '<span class="badge">' + esc(r.parsed?.ticket_type || '') + '</span>' +
              '</div>' +
              (r.target_ticket?.url ? '<span class="ticket-link" data-url="' + esc(r.target_ticket.url) + '">View in ' + esc(platformName.textContent || 'tracker') + ' →</span>' : '') +
            '</div>';
          addMsg(html, 'agent');
        } else {
          addMsg('Error: ' + esc(r.error || r.message || 'Unknown error'), 'error');
        }
        break;
      }

      case 'ticketList': {
        if (!msg.tickets?.length) { addMsg('No tickets found.', 'agent'); break; }
        const div = document.createElement('div');
        div.className = 'msg agent';
        div.innerHTML =
          '<div class="list-header">Recent Tickets</div>' +
          msg.tickets.map(t => {
            const assignee = t.assignedTo || 'Unassigned';
            return '<div class="ticket-row" data-url="' + esc(t.url || '') + '">' +
              avatarHtml(assignee) +
              '<span class="ticket-title-sm">' + esc(t.title) + '</span>' +
              '<span class="badge-sm">' + esc(t.status) + '</span>' +
            '</div>';
          }).join('');
        output.appendChild(div);
        output.scrollTop = output.scrollHeight;
        break;
      }

      case 'error':
        addMsg('Error: ' + esc(msg.message), 'error');
        break;

      case 'prefill':
        input.value = msg.text;
        input.focus();
        break;
    }
  });
</script>
</body>
</html>`;
    }
}
exports.TicketAgentPanel = TicketAgentPanel;
TicketAgentPanel.viewType = 'ticketAgent.panel';
//# sourceMappingURL=panel.js.map