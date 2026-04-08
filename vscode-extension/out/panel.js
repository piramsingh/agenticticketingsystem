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
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const api_client_1 = require("./api-client");
const config_1 = require("./config");
class TicketAgentPanel {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
        this._client = new api_client_1.ApiClient((0, config_1.getConfig)().backendUrl);
    }
    /** Called by VS Code when the sidebar view becomes visible. */
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };
        webviewView.webview.html = this._getHtml(webviewView.webview);
        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'createTicket':
                    await this._handleCreateTicket(message.text);
                    break;
                case 'listTickets':
                    await this._handleListTickets();
                    break;
                case 'listMembers':
                    await this._handleListMembers();
                    break;
                case 'healthCheck':
                    await this._handleHealthCheck();
                    break;
            }
        });
    }
    /** Called by the extension when user invokes "Create Ticket from Selection". */
    async prefillFromSelection(text) {
        this._view?.webview.postMessage({ command: 'prefill', text });
    }
    // ── Message handlers ────────────────────────────────────────────────────────
    async _handleCreateTicket(description) {
        this._postToWebview({ command: 'thinking' });
        try {
            // Re-read config in case the user changed the backend URL
            this._client = new api_client_1.ApiClient((0, config_1.getConfig)().backendUrl);
            const result = await this._client.createTicket(description);
            this._postToWebview({ command: 'ticketCreated', result });
        }
        catch (err) {
            this._postToWebview({
                command: 'error',
                message: `Failed to reach backend: ${err.message}`,
            });
        }
    }
    async _handleListTickets() {
        try {
            const tickets = await this._client.listRecentTickets(10);
            this._postToWebview({ command: 'ticketList', tickets });
        }
        catch (err) {
            this._postToWebview({ command: 'error', message: String(err) });
        }
    }
    async _handleListMembers() {
        try {
            const members = await this._client.listMembers();
            this._postToWebview({ command: 'memberList', members });
        }
        catch (err) {
            this._postToWebview({ command: 'error', message: String(err) });
        }
    }
    async _handleHealthCheck() {
        const ok = await this._client.healthCheck();
        this._postToWebview({ command: 'healthStatus', ok });
    }
    _postToWebview(msg) {
        this._view?.webview.postMessage(msg);
    }
    // ── HTML ────────────────────────────────────────────────────────────────────
    _getHtml(webview) {
        const htmlPath = path.join(this._extensionUri.fsPath, 'media', 'panel.html');
        if (fs.existsSync(htmlPath)) {
            return fs.readFileSync(htmlPath, 'utf8');
        }
        // Inline fallback if the file hasn't been built yet
        return this._inlineHtml();
    }
    _inlineHtml() {
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
  }
  .status { font-size: 11px; color: var(--vscode-descriptionForeground); }
  .status.ok   { color: #4caf50; }
  .status.err  { color: var(--vscode-errorForeground); }
  textarea {
    width: 100%;
    min-height: 80px;
    padding: 8px;
    border: 1px solid var(--vscode-input-border);
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border-radius: 4px;
    resize: vertical;
    font-family: inherit;
    font-size: inherit;
  }
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
  }
  #output {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    border: 1px solid var(--vscode-input-border);
    border-radius: 4px;
    font-size: 12px;
    white-space: pre-wrap;
    background: var(--vscode-editor-background);
  }
  .msg { margin-bottom: 8px; padding: 6px; border-radius: 4px; }
  .msg.user    { background: var(--vscode-inputOption-activeBackground); }
  .msg.agent   { background: var(--vscode-diffEditor-insertedLineBackground); }
  .msg.error   { background: var(--vscode-inputValidation-errorBackground); }
  .msg.loading { opacity: 0.6; font-style: italic; }
  a { color: var(--vscode-textLink-foreground); }
</style>
</head>
<body>

<div class="status" id="status">Checking backend...</div>
<textarea id="input" placeholder="Describe the ticket you want to create...&#10;&#10;e.g. High priority bug for Jamie — login breaks on Safari"></textarea>
<button id="btn-create">Create Ticket</button>
<button id="btn-list" class="secondary">Recent Tickets</button>
<div id="output"></div>

<script>
const vscode = acquireVsCodeApi();
const output = document.getElementById('output');
const input  = document.getElementById('input');
const status = document.getElementById('status');

function addMsg(text, type) {
  const div = document.createElement('div');
  div.className = 'msg ' + type;
  div.innerHTML = text.replace(/\\n/g, '<br>').replace(/(https?:\\/\\/[^\\s]+)/g, '<a href="$1">$1</a>');
  output.appendChild(div);
  output.scrollTop = output.scrollHeight;
  return div;
}

document.getElementById('btn-create').addEventListener('click', () => {
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, 'user');
  input.value = '';
  vscode.postMessage({ command: 'createTicket', text });
});

document.getElementById('btn-list').addEventListener('click', () => {
  vscode.postMessage({ command: 'listTickets' });
});

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    document.getElementById('btn-create').click();
  }
});

// Check backend health on load
vscode.postMessage({ command: 'healthCheck' });

window.addEventListener('message', e => {
  const msg = e.data;
  switch (msg.command) {
    case 'thinking':
      addMsg('Creating ticket...', 'loading');
      break;
    case 'ticketCreated':
      // Remove last loading msg
      const loading = output.querySelector('.loading');
      if (loading) loading.remove();
      if (msg.result.success) {
        addMsg(msg.result.message, 'agent');
      } else {
        addMsg('Error: ' + msg.result.error, 'error');
      }
      break;
    case 'ticketList':
      if (!msg.tickets || !msg.tickets.length) {
        addMsg('No recent tickets found.', 'agent');
        break;
      }
      const lines = msg.tickets.map(t =>
        '<b>' + t.id + '</b> ' + t.title + '\\n  ' + t.status + ' | ' + t.priority + ' | <a href="' + t.url + '">' + t.url + '</a>'
      ).join('\\n\\n');
      addMsg(lines, 'agent');
      break;
    case 'prefill':
      input.value = msg.text;
      input.focus();
      break;
    case 'error':
      addMsg('Error: ' + msg.message, 'error');
      break;
    case 'healthStatus':
      status.textContent = msg.ok ? 'Backend connected' : 'Backend offline — check settings';
      status.className = 'status ' + (msg.ok ? 'ok' : 'err');
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