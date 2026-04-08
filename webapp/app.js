const API_BASE_URL = 'http://localhost:8000';
let isProcessing = false;

// @mention state
let _members        = [];   // [{displayName, uniqueName}]
let _mentionActive  = false;
let _mentionIndex   = 0;
let _mentionQuery   = '';

const chatMessages    = () => document.getElementById('chatMessages');
const chatInput       = () => document.getElementById('chatInput');
const sendBtn         = () => document.getElementById('sendBtn');
const mentionDropdown = () => document.getElementById('mentionDropdown');

document.addEventListener('DOMContentLoaded', () => {
    chatInput().focus();
    chatInput().addEventListener('keydown', onInputKeydown);
    chatInput().addEventListener('input',   onInputChange);
    document.addEventListener('click', e => {
        if (!e.target.closest('.chat-input-wrap')) closeMention();
    });

    // Pre-fetch members so autocomplete is instant
    fetch(`${API_BASE_URL}/chat/members`)
        .then(r => r.json())
        .then(d => { _members = d.members || []; })
        .catch(() => {});
});

// ── @mention autocomplete ────────────────────────────────────────────────────

function onInputChange() {
    const val    = chatInput().value;
    const cursor = chatInput().selectionStart;

    // Find if cursor is inside an @word
    const before = val.slice(0, cursor);
    const match  = before.match(/@(\w*)$/);

    if (match) {
        _mentionQuery = match[1].toLowerCase();
        const results = _members.filter(m =>
            m.displayName.toLowerCase().includes(_mentionQuery) ||
            m.uniqueName.toLowerCase().includes(_mentionQuery)
        );
        if (results.length) {
            showMentionDropdown(results);
        } else {
            closeMention();
        }
    } else {
        closeMention();
    }
}

function onInputKeydown(e) {
    if (_mentionActive) {
        const items = mentionDropdown().querySelectorAll('.mention-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _mentionIndex = Math.min(_mentionIndex + 1, items.length - 1);
            items.forEach((el, i) => el.classList.toggle('active', i === _mentionIndex));
            return;
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            _mentionIndex = Math.max(_mentionIndex - 1, 0);
            items.forEach((el, i) => el.classList.toggle('active', i === _mentionIndex));
            return;
        }
        if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            const active = mentionDropdown().querySelector('.mention-item.active') || items[0];
            if (active) active.click();
            return;
        }
        if (e.key === 'Escape') { closeMention(); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
}

function showMentionDropdown(results) {
    _mentionActive = true;
    _mentionIndex  = 0;
    const dd = mentionDropdown();
    dd.innerHTML = '';
    results.forEach((m, i) => {
        const initials = m.displayName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        const item = document.createElement('div');
        item.className = 'mention-item' + (i === 0 ? ' active' : '');
        item.innerHTML = `<div class="mention-avatar">${initials}</div> ${m.displayName}`;
        item.addEventListener('mousedown', e => {
            e.preventDefault();   // prevent input blur
            insertMention(m.displayName);
        });
        dd.appendChild(item);
    });

    // Position above the input
    const inputEl = chatInput();
    dd.style.display = 'block';
    dd.style.bottom   = (inputEl.offsetHeight + 6) + 'px';
    dd.style.left     = '0';
}

function insertMention(displayName) {
    const input  = chatInput();
    const val    = input.value;
    const cursor = input.selectionStart;
    const before = val.slice(0, cursor);
    const after  = val.slice(cursor);

    // Replace the @partial with @FirstName
    const firstName = displayName.split(' ')[0];
    const replaced  = before.replace(/@\w*$/, `@${firstName} `);
    input.value = replaced + after;
    input.setSelectionRange(replaced.length, replaced.length);
    input.focus();
    closeMention();
}

function closeMention() {
    _mentionActive = false;
    _mentionIndex  = 0;
    mentionDropdown().style.display = 'none';
}

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
