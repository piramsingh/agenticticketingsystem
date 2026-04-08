/**
 * VS Code extension entry point.
 *
 * Registers:
 *   - Sidebar webview (ticketAgent.panel) via TicketAgentPanel provider
 *   - Command: ticketAgent.openPanel  — reveal the sidebar
 *   - Command: ticketAgent.createTicket — pre-fill panel with selected text
 */
import * as vscode from 'vscode';
import { TicketAgentPanel } from './panel';

export function activate(context: vscode.ExtensionContext): void {
  const provider = new TicketAgentPanel(context.extensionUri);

  // Register the sidebar webview provider
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      TicketAgentPanel.viewType,
      provider,
      { webviewOptions: { retainContextWhenHidden: true } },
    ),
  );

  // Command: open / focus the panel
  context.subscriptions.push(
    vscode.commands.registerCommand('ticketAgent.openPanel', () => {
      vscode.commands.executeCommand('ticketAgent.panel.focus');
    }),
  );

  // Command: create ticket from the current editor selection
  context.subscriptions.push(
    vscode.commands.registerCommand('ticketAgent.createTicket', async () => {
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
    }),
  );
}

export function deactivate(): void {
  // Nothing to clean up — the extension host tears down subscriptions automatically
}
