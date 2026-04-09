"use strict";
/**
 * Thin HTTP client that calls the Ticket Agent FastAPI backend.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiClient = void 0;
class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }
    async createTicket(description) {
        return this._post('/chat', { message: description });
    }
    async getTicket(ticketId) {
        return this._get(`/tickets/${encodeURIComponent(ticketId)}`);
    }
    async listRecentTickets(limit = 10) {
        return this._get(`/tickets?limit=${limit}`);
    }
    async listMembers() {
        const data = await this._get('/chat/members');
        return data.members ?? [];
    }
    async healthCheck() {
        try {
            const resp = await fetch(`${this.baseUrl}/health`);
            return resp.ok;
        }
        catch {
            return false;
        }
    }
    async _get(path) {
        const resp = await fetch(`${this.baseUrl}${path}`);
        if (!resp.ok) {
            throw new Error(`GET ${path} failed: ${resp.status} ${resp.statusText}`);
        }
        return resp.json();
    }
    async _post(path, body) {
        const resp = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            throw new Error(`POST ${path} failed: ${resp.status} ${resp.statusText}`);
        }
        return resp.json();
    }
}
exports.ApiClient = ApiClient;
//# sourceMappingURL=api-client.js.map