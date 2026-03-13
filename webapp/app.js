const API_BASE_URL = 'http://localhost:8000';
let isProcessing = false;

const chatMessages = () => document.getElementById('chatMessages');
const chatInput    = () => document.getElementById('chatInput');
const sendBtn      = () => document.getElementById('sendBtn');

document.addEventListener('DOMContentLoaded', () => {
    chatInput().focus();
    chatInput().addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    });
});

async function handleSend() {
    const input = chatInput();
    const message = input.value.trim();
    if (!message || isProcessing) return;

    addMsg(message, 'user');
    input.value = '';
    setProcessing(true);

    const typingId = showTyping();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        removeTyping(typingId);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (data.success) {
            showSuccess(data);
        } else {
            addMsg(`❌ ${data.message || 'Could not create ticket. Try again.'}`, 'bot');
        }
    } catch (err) {
        removeTyping(typingId);
        addMsg('❌ Could not reach the server. Make sure the backend is running.', 'bot');
    } finally {
        setProcessing(false);
        input.focus();
    }
}

function showSuccess(data) {
    const { parsed, target_ticket, jama_requirement } = data;

    const ticketId   = target_ticket?.id    ?? '—';
    const ticketUrl  = target_ticket?.url  ?? null;
    const title      = parsed?.title       ?? parsed?.description ?? 'Work Item';
    const assignee   = parsed?.assignee    ?? 'Unassigned';
    const priority   = parsed?.priority    ?? 'Medium';
    const type       = parsed?.ticket_type ?? parsed?.type ?? 'Issue';
    const jamaId     = jama_requirement?.id ?? null;

    const card = document.createElement('div');
    card.className = 'ticket-card';
    card.innerHTML = `
        <div class="tc-header">✅ Ticket created</div>
        <div class="tc-row">📌 <strong>#${ticketId}</strong> — <a href="${ticketUrl}" target="_blank">View in Azure DevOps ↗</a></div>
        ${assignee ? `<div class="tc-row">👤 Assigned to ${assignee}</div>` : ''}
        <div class="tc-row">⚡ ${priority} priority · ${type}</div>
        <div class="system-badges">
            <span class="sys-badge synced">Azure DevOps ✓</span>
            ${jamaId ? `<span class="sys-badge synced">Jama Connect #${jamaId} ✓</span>` : '<span class="sys-badge">Jama Connect (mock)</span>'}
        </div>
    `;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.style.maxWidth = '90%';
    bubble.appendChild(card);

    const msg = document.createElement('div');
    msg.className = 'msg bot';
    msg.innerHTML = `<div class="avatar bot">AI</div>`;
    msg.appendChild(bubble);

    chatMessages().appendChild(msg);
    scrollBottom();
}

function addMsg(text, sender) {
    const msg = document.createElement('div');
    msg.className = `msg ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar ${sender}`;
    avatar.textContent = sender === 'bot' ? 'AI' : 'You';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = text.replace(/\n/g, '<br>');

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatMessages().appendChild(msg);
    scrollBottom();
}

function showTyping() {
    const id = 'typing-' + Date.now();
    const msg = document.createElement('div');
    msg.className = 'msg bot';
    msg.id = id;
    msg.innerHTML = `
        <div class="avatar bot">AI</div>
        <div class="bubble">
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatMessages().appendChild(msg);
    scrollBottom();
    return id;
}

function removeTyping(id) {
    document.getElementById(id)?.remove();
}

function setProcessing(val) {
    isProcessing = val;
    sendBtn().disabled = val;
    sendBtn().textContent = val ? '...' : 'Send →';
}

function scrollBottom() {
    const el = chatMessages();
    el.scrollTop = el.scrollHeight;
}

function fillExample(btn) {
    // strip leading emoji + space
    const text = btn.textContent.replace(/^[\p{Emoji}\s]+/u, '').trim();
    chatInput().value = text;
    chatInput().focus();
}

window.handleSend  = handleSend;
window.fillExample = fillExample;
