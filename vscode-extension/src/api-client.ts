/**
 * Thin HTTP client that calls the Ticket Agent FastAPI backend.
 */

export interface CreateTicketResponse {
  success: boolean;
  message: string;
  target_ticket?: { id: string; url: string; created_at: string };
  error?: string;
}

export interface Ticket {
  id: string;
  title: string;
  status: string;
  priority: string;
  assignedTo: string;
  url: string;
}

export interface Member {
  displayName: string;
  uniqueName: string;
}

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  async createTicket(description: string): Promise<CreateTicketResponse> {
    return this._post<CreateTicketResponse>('/chat', { message: description });
  }

  async getTicket(ticketId: string): Promise<Ticket> {
    return this._get<Ticket>(`/tickets/${encodeURIComponent(ticketId)}`);
  }

  async listRecentTickets(limit = 10): Promise<Ticket[]> {
    return this._get<Ticket[]>(`/tickets?limit=${limit}`);
  }

  async listMembers(): Promise<Member[]> {
    const data = await this._get<{ members: Member[] }>('/chat/members');
    return data.members ?? [];
  }

  async healthCheck(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/health`);
      return resp.ok;
    } catch {
      return false;
    }
  }

  private async _get<T>(path: string): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`);
    if (!resp.ok) {
      throw new Error(`GET ${path} failed: ${resp.status} ${resp.statusText}`);
    }
    return resp.json() as Promise<T>;
  }

  private async _post<T>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    if (!resp.ok) {
      throw new Error(`POST ${path} failed: ${resp.status} ${resp.statusText}`);
    }
    return resp.json() as Promise<T>;
  }
}
