import * as vscode from 'vscode';

export interface ExtensionConfig {
  backendUrl: string;
  anthropicApiKey: string;
}

export function getConfig(): ExtensionConfig {
  const cfg = vscode.workspace.getConfiguration('ticketAgent');
  return {
    backendUrl:      cfg.get<string>('backendUrl', 'http://localhost:8000'),
    anthropicApiKey: cfg.get<string>('anthropicApiKey', ''),
  };
}
