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
                case 'retryConnection':
                    await this._loadStatus();
                    await this._loadMembers();
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
                connectorType: d?.connector_type ?? '',
            });
        }
        catch {
            this._post({ command: 'connectorStatus', connected: false, displayName: 'Offline', color: '#888', project: '', connectorType: '' });
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
        this._post({ command: 'ticketListLoading' });
        try {
            const tickets = await this._request('/tickets?limit=8');
            this._post({ command: 'ticketList', tickets: Array.isArray(tickets) ? tickets : [] });
        }
        catch (e) {
            this._post({ command: 'ticketList', tickets: [] }); // clears skeleton, shows empty state
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
  /* Platform selector — pills row */
  .platform-selector {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }
  .platform-pill {
    display: flex; align-items: center; justify-content: center;
    gap: 5px; padding: 7px 4px; border-radius: 8px;
    background: linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.06);
    font-size: 10px; font-weight: 600;
    color: var(--vscode-descriptionForeground);
    cursor: default; user-select: none;
    transition: all 0.18s ease;
  }
  .platform-pill .pill-dot {
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; opacity: 0.5;
  }
  .platform-pill.active {
    background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03));
    border-color: rgba(255,255,255,0.18);
    color: var(--vscode-foreground);
    box-shadow:
      0 4px 14px rgba(0,0,0,0.20),
      inset 0 1px 0 rgba(255,255,255,0.08);
  }
  .platform-pill.active .pill-dot { opacity: 1; box-shadow: 0 0 6px currentColor; }

  /* Platform status line */
  .platform-bar {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 8px; font-size: 11px;
    color: var(--vscode-descriptionForeground);
  }
  .platform-dot {
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
  }
  .platform-name { flex: 1; }
  .platform-project { font-size: 10px; font-weight: 400; opacity: 0.75; }

  /* Input area */
  .input-wrap { position: relative; }
  textarea {
    width: 100%;
    min-height: 60px;
    max-height: 200px;
    padding: 8px;
    border: 1px solid var(--vscode-input-border);
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border-radius: 4px;
    resize: none;
    font-family: inherit;
    font-size: inherit;
    overflow-y: auto;
  }
  textarea:focus { outline: 1px solid var(--vscode-focusBorder); }
  textarea::placeholder { color: var(--vscode-input-placeholderForeground); opacity: 0.7; }

  /* Offline banner */
  .offline-banner {
    display: none;
    padding: 6px 10px;
    background: var(--vscode-inputValidation-warningBackground);
    color: var(--vscode-inputValidation-warningForeground);
    border: 1px solid var(--vscode-inputValidation-warningBorder);
    border-radius: 4px;
    font-size: 11px;
    line-height: 1.4;
  }
  .offline-banner.visible { display: block; }
  .offline-banner .retry-link {
    color: var(--vscode-textLink-foreground);
    cursor: pointer;
    text-decoration: underline;
    margin-left: 4px;
  }

  /* Empty state */
  .empty-state {
    display: flex; flex-direction: column; align-items: center;
    padding: 24px 12px; gap: 8px;
    color: var(--vscode-descriptionForeground);
    text-align: center;
  }
  .empty-state .icon { font-size: 24px; opacity: 0.6; }
  .empty-state .label { font-size: 12px; font-weight: 600; }
  .empty-state .hint { font-size: 11px; opacity: 0.8; }

  /* Loading skeleton */
  .skeleton-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 4px;
  }
  .skeleton {
    background: linear-gradient(90deg,
      var(--vscode-list-hoverBackground) 0%,
      var(--vscode-list-activeSelectionBackground) 50%,
      var(--vscode-list-hoverBackground) 100%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
    border-radius: 4px;
    opacity: 0.5;
  }
  .skeleton-circle { width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0; }
  .skeleton-line { height: 12px; flex: 1; }
  @keyframes shimmer {
    0%   { background-position: 100% 50%; }
    100% { background-position: -100% 50%; }
  }

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

  /* Liquid glass buttons */
  button {
    width: 100%;
    padding: 9px 14px;
    background: linear-gradient(135deg,
      rgba(120, 160, 255, 0.18),
      rgba(120, 160, 255, 0.06));
    color: var(--vscode-foreground);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
    cursor: pointer;
    font-size: inherit;
    font-weight: 500;
    -webkit-backdrop-filter: blur(12px);
    backdrop-filter: blur(12px);
    box-shadow:
      0 4px 16px rgba(0, 0, 0, 0.18),
      inset 0 1px 0 rgba(255, 255, 255, 0.10);
    transition: all 0.18s ease;
    position: relative;
    overflow: hidden;
  }
  button:hover {
    background: linear-gradient(135deg,
      rgba(140, 175, 255, 0.28),
      rgba(140, 175, 255, 0.10));
    border-color: rgba(255, 255, 255, 0.18);
    transform: translateY(-1px);
    box-shadow:
      0 6px 20px rgba(0, 0, 0, 0.24),
      inset 0 1px 0 rgba(255, 255, 255, 0.16);
  }
  button:active {
    transform: translateY(0);
    box-shadow:
      0 2px 8px rgba(0, 0, 0, 0.18),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }
  button.secondary {
    background: linear-gradient(135deg,
      rgba(255, 255, 255, 0.06),
      rgba(255, 255, 255, 0.02));
    margin-top: 4px;
  }
  button.secondary:hover {
    background: linear-gradient(135deg,
      rgba(255, 255, 255, 0.10),
      rgba(255, 255, 255, 0.04));
  }

  /* Chat feed */
  #output {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 4px 2px;
  }

  /* User message — right-aligned bubble */
  .msg.user {
    align-self: flex-end;
    max-width: 85%;
    padding: 8px 12px;
    background: linear-gradient(135deg, rgba(120,160,255,0.20), rgba(120,160,255,0.08));
    border: 1px solid rgba(120,160,255,0.18);
    border-radius: 14px 14px 4px 14px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--vscode-foreground);
    -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
  }

  /* Assistant message — left-aligned bubble (mirrors the user bubble) */
  .msg.system {
    align-self: flex-start;
    max-width: 85%;
    padding: 8px 12px;
    background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px 14px 14px 4px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--vscode-foreground);
    -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
  }
  .msg.system .ticket-link {
    color: var(--vscode-textLink-foreground);
    cursor: pointer;
    font-weight: 600;
    text-decoration: none;
  }
  .msg.system .ticket-link:hover { text-decoration: underline; }

  /* Loading "thinking" indicator */
  .msg.loading {
    align-self: flex-start;
    font-size: 11px;
    color: var(--vscode-descriptionForeground);
    font-style: italic;
    padding: 4px 8px;
  }

  /* Error message — system-style but red-tinted */
  .msg.error {
    align-self: center;
    font-size: 11px;
    padding: 6px 10px;
    color: var(--vscode-errorForeground, #f48771);
    background: rgba(244, 135, 113, 0.08);
    border: 1px solid rgba(244, 135, 113, 0.20);
    border-radius: 6px;
    max-width: 90%;
  }

  /* Input row — pinned at bottom */
  .input-row {
    display: flex; align-items: flex-end; gap: 6px;
  }
  .input-row .input-wrap { flex: 1; }
  .send-btn {
    padding: 0 !important;
    height: 36px;
    width: 36px !important;
    min-width: 36px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50% !important;
    flex-shrink: 0;
    font-size: 16px;
    font-weight: 700;
    line-height: 1;
  }

  /* Top-right action row inside Chat panel */
  .chat-actions {
    display: flex; justify-content: flex-end;
    padding: 0 2px;
  }
  .action-link {
    font-size: 11px;
    color: var(--vscode-textLink-foreground);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .action-link:hover { background: var(--vscode-list-hoverBackground); }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    padding-bottom: 0;
  }
  .tab {
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 500;
    color: var(--vscode-descriptionForeground);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.15s ease;
    user-select: none;
  }
  .tab:hover { color: var(--vscode-foreground); }
  .tab.active {
    color: var(--vscode-foreground);
    border-bottom-color: rgba(120, 160, 255, 0.7);
  }
  .tab-panel { display: none; flex: 1; flex-direction: column; gap: 8px; min-height: 0; }
  .tab-panel.active { display: flex; }

  /* Suggestion cards */
  .bulk-bar {
    display: flex; align-items: center; justify-content: space-between;
    gap: 8px; padding: 4px 2px;
    font-size: 11px; color: var(--vscode-descriptionForeground);
  }
  .bulk-bar button { width: auto; padding: 6px 12px; font-size: 11px; }
  .bulk-bar.disabled { opacity: 0.4; pointer-events: none; }

  .suggestions-list {
    flex: 1; overflow-y: auto;
    display: flex; flex-direction: column; gap: 8px;
  }

  .suggestion-card {
    display: flex; flex-direction: column; gap: 6px;
    padding: 10px;
    background: linear-gradient(135deg,
      rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    transition: all 0.15s ease;
  }
  .suggestion-card:hover { border-color: rgba(255,255,255,0.12); }
  .suggestion-card.selected {
    border-color: rgba(120, 160, 255, 0.6);
    background: linear-gradient(135deg,
      rgba(120, 160, 255, 0.10), rgba(120, 160, 255, 0.02));
  }
  .suggestion-card.created {
    opacity: 0.4;
    border-color: rgba(120, 220, 140, 0.3);
  }

  .suggestion-header {
    display: flex; align-items: flex-start; gap: 8px;
  }
  .suggestion-checkbox {
    margin-top: 2px;
    width: 14px; height: 14px;
    cursor: pointer;
    accent-color: rgba(120, 160, 255, 0.9);
  }
  .suggestion-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .suggestion-title {
    font-size: 12px; font-weight: 600;
    color: var(--vscode-foreground);
    line-height: 1.4;
  }
  .suggestion-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .suggestion-type {
    font-size: 10px; padding: 1px 6px; border-radius: 8px;
    background: rgba(120, 160, 255, 0.18);
    color: var(--vscode-foreground);
    font-weight: 600;
  }
  .suggestion-location {
    font-size: 10px;
    color: var(--vscode-descriptionForeground);
    font-family: var(--vscode-editor-font-family, monospace);
  }
  .suggestion-snippet {
    font-size: 11px;
    color: var(--vscode-descriptionForeground);
    background: rgba(0,0,0,0.18);
    padding: 5px 8px;
    border-radius: 5px;
    font-family: var(--vscode-editor-font-family, monospace);
    line-height: 1.4;
    overflow-x: auto;
    white-space: pre;
  }
  .suggestion-actions { display: flex; gap: 6px; justify-content: flex-end; }
  .suggestion-actions button {
    width: auto; padding: 5px 12px; font-size: 11px;
    border-radius: 7px;
  }
  .suggestion-actions button.dismiss {
    background: linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
  }

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

<div class="platform-selector" id="platform-selector">
  <div class="platform-pill" data-platform="jira">
    <div class="pill-dot" style="background:#0052CC;color:#0052CC"></div>
    <span>Jira</span>
  </div>
  <div class="platform-pill" data-platform="azure_devops">
    <div class="pill-dot" style="background:#0078D4;color:#0078D4"></div>
    <span>Azure</span>
  </div>
  <div class="platform-pill" data-platform="github_issues">
    <div class="pill-dot" style="background:#8B949E;color:#8B949E"></div>
    <span>GitHub</span>
  </div>
  <div class="platform-pill" data-platform="linear">
    <div class="pill-dot" style="background:#5E6AD2;color:#5E6AD2"></div>
    <span>Linear</span>
  </div>
</div>

<div class="platform-bar" id="platform-bar">
  <div class="platform-dot" id="platform-dot" style="background:#888"></div>
  <span class="platform-name" id="platform-name">Connecting...</span>
  <span class="platform-project" id="platform-project"></span>
</div>

<div class="offline-banner" id="offline-banner">
  Backend not reachable on localhost:8000.
  <span class="retry-link" id="retry-link">Retry</span>
</div>

<div class="tabs">
  <div class="tab active" data-tab="chat">Chat</div>
  <div class="tab" data-tab="suggestions">Suggestions</div>
</div>

<div class="tab-panel active" data-panel="chat">
  <div class="chat-actions">
    <span class="action-link" id="btn-list">Recent tickets</span>
  </div>
  <div id="output"></div>
  <div class="input-row">
    <div class="input-wrap">
      <div id="mention-dropdown"></div>
      <textarea id="input" placeholder="Describe a ticket — Enter to send, Shift+Enter for newline"></textarea>
    </div>
    <button id="btn-create" class="send-btn" title="Send">↑</button>
  </div>
</div>

<div class="tab-panel" data-panel="suggestions">
  <button id="btn-scan">Scan Codebase</button>
  <div class="bulk-bar disabled" id="bulk-bar">
    <span id="bulk-count">0 selected</span>
    <button id="btn-bulk-create" class="secondary">Create Selected</button>
  </div>
  <div class="suggestions-list" id="suggestions-list">
    <div class="empty-state">
      <div class="icon">🔎</div>
      <div class="label">No scan run yet</div>
      <div class="hint">Scan your codebase to surface work that needs doing.</div>
    </div>
  </div>
</div>

<script>
  const vscode      = acquireVsCodeApi();
  const output      = document.getElementById('output');
  const input       = document.getElementById('input');
  const platformDot = document.getElementById('platform-dot');
  const platformName = document.getElementById('platform-name');
  const platformProject = document.getElementById('platform-project');
  const dropdown    = document.getElementById('mention-dropdown');
  const offlineBanner = document.getElementById('offline-banner');
  const retryLink     = document.getElementById('retry-link');

  let members = [];
  let mentionStart = -1;
  let activeIdx = 0;

  // ── Auto-resize textarea ──────────────────────────────────────────────────
  function autosize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
  }
  input.addEventListener('input', autosize);

  // ── Retry connection ──────────────────────────────────────────────────────
  retryLink.addEventListener('click', () => {
    offlineBanner.classList.remove('visible');
    platformName.textContent = 'Connecting...';
    vscode.postMessage({ command: 'retryConnection' });
  });

  // ── Tabs ──────────────────────────────────────────────────────────────────
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector('.tab-panel[data-panel="' + target + '"]').classList.add('active');
    });
  });

  // ── Suggestions (mock data — backend wires up next week) ──────────────────
  const suggestionsList = document.getElementById('suggestions-list');
  const bulkBar         = document.getElementById('bulk-bar');
  const bulkCount       = document.getElementById('bulk-count');
  const btnScan         = document.getElementById('btn-scan');
  const btnBulkCreate   = document.getElementById('btn-bulk-create');

  // TODO(backend): replace this with real GET /scan/suggestions response
  const MOCK_SUGGESTIONS = [
    {
      id: 's1', type: 'Task',
      title: 'Implement retry logic for connector init failures',
      file: 'src/main.py', line: 67,
      snippet: '# TODO: retry validate_connection on transient failure'
    },
    {
      id: 's2', type: 'Bug',
      title: 'Sprint assignment can race with issue creation in fast paths',
      file: 'src/connectors/jira.py', line: 142,
      snippet: 'sprint_id = await self._get_active_sprint_id()'
    },
    {
      id: 's3', type: 'Task',
      title: 'Add unit tests for _resolve_issue_type fallback branches',
      file: 'src/connectors/jira.py', line: 318,
      snippet: 'async def _resolve_issue_type(self, requested: str) -> str:'
    },
    {
      id: 's4', type: 'Refactor',
      title: 'Extract OpenRouter model list to config',
      file: 'src/agent/ticket_parser.py', line: 226,
      snippet: '_MODEL_FALLBACKS = [\\n    "google/gemma-4-26b-a4b-it:free",'
    },
    {
      id: 's5', type: 'Bug',
      title: 'GitHub label collisions are silently dropped on 422 retry',
      file: 'src/connectors/github_issues.py', line: 100,
      snippet: 'body.pop("labels")'
    },
  ];

  let suggestions = [];

  function renderSuggestions() {
    if (!suggestions.length) {
      suggestionsList.innerHTML =
        '<div class="empty-state">' +
          '<div class="icon">✓</div>' +
          '<div class="label">All caught up</div>' +
          '<div class="hint">No suggestions right now. Run another scan to refresh.</div>' +
        '</div>';
      updateBulkBar();
      return;
    }

    suggestionsList.innerHTML = suggestions.map(s => {
      return '<div class="suggestion-card" data-id="' + s.id + '">' +
        '<div class="suggestion-header">' +
          '<input type="checkbox" class="suggestion-checkbox" data-id="' + s.id + '">' +
          '<div class="suggestion-body">' +
            '<div class="suggestion-title">' + esc(s.title) + '</div>' +
            '<div class="suggestion-meta">' +
              '<span class="suggestion-type">' + esc(s.type) + '</span>' +
              '<span class="suggestion-location">' + esc(s.file) + ':' + s.line + '</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="suggestion-snippet">' + esc(s.snippet) + '</div>' +
        '<div class="suggestion-actions">' +
          '<button class="dismiss" data-action="dismiss" data-id="' + s.id + '">Dismiss</button>' +
          '<button data-action="create" data-id="' + s.id + '">Create</button>' +
        '</div>' +
      '</div>';
    }).join('');
    updateBulkBar();
  }

  function updateBulkBar() {
    const checked = suggestionsList.querySelectorAll('.suggestion-checkbox:checked').length;
    bulkCount.textContent = checked + ' selected';
    bulkBar.classList.toggle('disabled', checked === 0);
  }

  function suggestionToPrompt(s) {
    return 'Create a ' + s.type.toLowerCase() + ': ' + s.title +
           ' (found at ' + s.file + ':' + s.line + ')';
  }

  btnScan.addEventListener('click', () => {
    suggestionsList.innerHTML =
      '<div class="empty-state">' +
        '<div class="icon">⏳</div>' +
        '<div class="label">Scanning...</div>' +
        '<div class="hint">Looking for TODOs, missing tests, refactors, and more.</div>' +
      '</div>';
    // TODO(backend): swap setTimeout for vscode.postMessage({ command: 'scanCodebase' })
    setTimeout(() => {
      suggestions = MOCK_SUGGESTIONS.slice();
      renderSuggestions();
    }, 800);
  });

  btnBulkCreate.addEventListener('click', () => {
    const selected = Array.from(suggestionsList.querySelectorAll('.suggestion-checkbox:checked'))
      .map(cb => cb.getAttribute('data-id'));
    selected.forEach(id => createSuggestion(id));
  });

  function createSuggestion(id) {
    const s = suggestions.find(x => x.id === id);
    if (!s) return;
    const card = suggestionsList.querySelector('.suggestion-card[data-id="' + id + '"]');
    if (card) { card.classList.add('created'); }
    vscode.postMessage({ command: 'createTicket', text: suggestionToPrompt(s) });
  }

  function dismissSuggestion(id) {
    suggestions = suggestions.filter(x => x.id !== id);
    renderSuggestions();
  }

  // Event delegation for suggestion checkboxes and buttons
  suggestionsList.addEventListener('change', e => {
    const cb = e.target.closest('.suggestion-checkbox');
    if (!cb) return;
    const card = cb.closest('.suggestion-card');
    if (card) { card.classList.toggle('selected', cb.checked); }
    updateBulkBar();
  });

  suggestionsList.addEventListener('click', e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const id = btn.getAttribute('data-id');
    if (btn.getAttribute('data-action') === 'create') {
      createSuggestion(id);
    } else if (btn.getAttribute('data-action') === 'dismiss') {
      dismissSuggestion(id);
    }
  });

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
    // Enter sends, Shift+Enter inserts a newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
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
        offlineBanner.classList.toggle('visible', !msg.connected);
        // Highlight the active platform pill
        document.querySelectorAll('.platform-pill').forEach(p => p.classList.remove('active'));
        if (msg.connected && msg.connectorType) {
          const active = document.querySelector('.platform-pill[data-platform="' + msg.connectorType + '"]');
          if (active) { active.classList.add('active'); }
        }
        break;

      case 'membersLoaded':
        members = msg.members || [];
        break;

      case 'thinking':
        addMsg('Creating ticket…', 'loading');
        break;

      case 'ticketCreated': {
        const loading = output.querySelector('.loading');
        if (loading) { loading.remove(); }
        const r = msg.result;
        if (r.success && r.target_ticket) {
          const id     = esc(r.target_ticket.id || '');
          const url    = r.target_ticket.url || '';
          const title  = esc(r.parsed?.title || '');
          const idHtml = url
            ? '<span class="ticket-link" data-url="' + esc(url) + '">#' + id + '</span>'
            : '#' + id;
          const body = title
            ? 'Got it — created ' + idHtml + ': ' + title
            : 'Got it — created ' + idHtml;
          addMsg(body, 'system');
        } else {
          addMsg(esc(r.error || r.message || 'Failed to create ticket'), 'error');
        }
        break;
      }

      case 'ticketListLoading': {
        // Remove any prior skeleton/list before rendering a fresh skeleton
        output.querySelectorAll('.skeleton-list').forEach(el => el.remove());
        const div = document.createElement('div');
        div.className = 'msg agent skeleton-list';
        let skel = '<div class="list-header">Loading tickets...</div>';
        for (let i = 0; i < 4; i++) {
          skel +=
            '<div class="skeleton-row">' +
              '<div class="skeleton skeleton-circle"></div>' +
              '<div class="skeleton skeleton-line"></div>' +
            '</div>';
        }
        div.innerHTML = skel;
        output.appendChild(div);
        output.scrollTop = output.scrollHeight;
        break;
      }

      case 'ticketList': {
        // Replace skeleton (if present) with real content
        const skeleton = output.querySelector('.skeleton-list');
        if (skeleton) { skeleton.remove(); }

        if (!msg.tickets?.length) {
          const empty = document.createElement('div');
          empty.className = 'msg agent';
          empty.innerHTML =
            '<div class="empty-state">' +
              '<div class="icon">📋</div>' +
              '<div class="label">No tickets yet</div>' +
              '<div class="hint">Create one above to get started.</div>' +
            '</div>';
          output.appendChild(empty);
          output.scrollTop = output.scrollHeight;
          break;
        }

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