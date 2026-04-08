"use strict";
/**
 * Thin HTTP client that calls the Ticket Agent FastAPI backend.
 * All network calls are centralised here so the rest of the extension
 * never has to think about fetch / error handling.
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
        return this._get('/members');
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