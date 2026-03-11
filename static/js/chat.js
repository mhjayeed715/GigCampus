// chat.js - Socket.IO client for the chat window
// used the Flask-SocketIO docs for connect/emit basics,
// Copilot helped me fix a DOM selector issue with dynamic messages

(function () {
    'use strict';

    const config = window.CHAT_CONFIG;
    if (!config) return;

    // Connect to Socket.IO server
    const socket = io();

    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const msgInput = document.getElementById('msg-input');
    const sendOfferBtn = document.getElementById('send-offer-btn');

    // --- Join room ---
    socket.emit('join', { conversation_id: config.conversationId });

    // --- Send text message ---
    chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const body = msgInput.value.trim();
        if (!body) return;

        socket.emit('send_message', {
            conversation_id: config.conversationId,
            body: body,
            msg_type: 'text'
        });

        msgInput.value = '';
        msgInput.focus();
    });

    // --- Send an offer ---
    if (sendOfferBtn) {
        sendOfferBtn.addEventListener('click', function () {
            const amount = document.getElementById('offer-amount').value;
            const message = document.getElementById('offer-message').value.trim();

            if (!amount || parseInt(amount) <= 0) {
                alert('Please enter a valid amount.');
                return;
            }

            socket.emit('send_message', {
                conversation_id: config.conversationId,
                body: message || 'I\'d like to offer this price.',
                msg_type: 'offer',
                offer_amount: parseInt(amount)
            });

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('offerModal'));
            if (modal) modal.hide();

            // Clear inputs
            document.getElementById('offer-amount').value = '';
            document.getElementById('offer-message').value = '';
        });
    }

    // --- Receive messages ---
    socket.on('new_message', function (data) {
        appendMessage(data);
        scrollToBottom();
    });

    socket.on('offer_accepted', function (data) {
        window.location.href = '/orders/' + data.order_id;
    });

    socket.on('status', function (data) {
        const div = document.createElement('div');
        div.className = 'text-center text-muted small my-2';
        div.textContent = data.msg;
        chatMessages.appendChild(div);
        scrollToBottom();
    });

    // append a message bubble to the chat area
    function appendMessage(data) {
        const wrapper = document.createElement('div');
        wrapper.className = 'mb-3 d-flex ' +
            (data.sender_id === config.currentUserId ? 'justify-content-end' : '');

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble rounded p-3 ' +
            (data.sender_id === config.currentUserId ? 'bg-warning text-dark' : 'bg-light');
        bubble.style.maxWidth = '70%';

        // Header (name + time)
        const header = document.createElement('div');
        header.className = 'd-flex justify-content-between mb-1';
        header.innerHTML = `<small class="fw-bold">${data.sender_name}</small>
                            <small class="text-muted ms-2">${data.created_at.substring(11, 16)}</small>`;
        bubble.appendChild(header);

        // Body
        if (data.msg_type === 'offer') {
            const offerDiv = document.createElement('div');
            offerDiv.className = 'alert alert-info mb-1 p-2';
            offerDiv.innerHTML = `<i class="bi bi-tag"></i> <strong>Offer: ${formatBdt(data.offer_amount)}</strong>
                                  <p class="mb-0 small">${data.body}</p>`;

            // Show accept button if I'm not the sender
            if (data.sender_id !== config.currentUserId) {
                const btnDiv = document.createElement('div');
                btnDiv.className = 'mt-2';
                const acceptBtn = document.createElement('button');
                acceptBtn.className = 'btn btn-success btn-sm accept-offer-btn';
                acceptBtn.dataset.messageId = data.id;
                acceptBtn.innerHTML = '<i class="bi bi-check"></i> Accept';
                const declineBtn = document.createElement('button');
                declineBtn.className = 'btn btn-outline-secondary btn-sm ms-1';
                declineBtn.textContent = 'Decline';
                btnDiv.appendChild(acceptBtn);
                btnDiv.appendChild(declineBtn);
                offerDiv.appendChild(btnDiv);
            }

            bubble.appendChild(offerDiv);
        } else {
            const bodyP = document.createElement('p');
            bodyP.className = 'mb-0';
            bodyP.textContent = data.body;
            bubble.appendChild(bodyP);
        }

        wrapper.appendChild(bubble);
        chatMessages.appendChild(wrapper);
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatBdt(amount) {
        return new Intl.NumberFormat().format(amount) + ' BDT';
    }

    // event delegation for accept buttons
    chatMessages.addEventListener('click', function (e) {
        const btn = e.target.closest('.accept-offer-btn');
        if (!btn) return;

        const messageId = parseInt(btn.dataset.messageId);
        socket.emit('accept_offer', { message_id: messageId });
        btn.disabled = true;
        btn.textContent = 'Accepting...';
    });

    // Scroll to bottom on page load
    scrollToBottom();
})();
