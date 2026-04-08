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
exports.activate = activate;
exports.deactivate = deactivate;
/**
 * VS Code extension entry point.
 *
 * Registers:
 *   - Sidebar webview (ticketAgent.panel) via TicketAgentPanel provider
 *   - Command: ticketAgent.openPanel  — reveal the sidebar
 *   - Command: ticketAgent.createTicket — pre-fill panel with selected text
 */
const vscode = __importStar(require("vscode"));
const panel_1 = require("./panel");
function activate(context) {
    const provider = new panel_1.TicketAgentPanel(context.extensionUri);
    // Register the sidebar webview provider
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(panel_1.TicketAgentPanel.viewType, provider, { webviewOptions: { retainContextWhenHidden: true } }));
    // Command: open / focus the panel
    context.subscriptions.push(vscode.commands.registerCommand('ticketAgent.openPanel', () => {
        vscode.commands.executeCommand('ticketAgent.panel.focus');
    }));
    // Command: create ticket from the current editor selection
    context.subscriptions.push(vscode.commands.registerCommand('ticketAgent.createTicket', async () => {
        const editor = vscode.window.activeTextEditor;
        let prefill = '';
        if (editor && !editor.selection.isEmpty) {
            const selectedText = editor.document.getText(editor.selection);
            const filePath = vscode.workspace.asRelativePath(editor.document.uri);
            prefill = `Bug in ${filePath}: ${selectedText.substring(0, 200)}`;
        }
        // Focus the sidebar, then pre-fill if we have selected text
        await vscode.commands.executeCommand('ticketAgent.panel.focus');
        if (prefill) {
            // Small delay to ensure the webview is ready
            setTimeout(() => provider.prefillFromSelection(prefill), 300);
        }
    }));
}
function deactivate() {
    // Nothing to clean up — the extension host tears down subscriptions automatically
}
//# sourceMappingURL=extension.js.map