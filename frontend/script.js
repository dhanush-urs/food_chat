/**
 * FoodFlow Support Bot — script.js
 * Handles chat logic, API calls, and dynamic card rendering.
 * Vanilla JS only — no frameworks.
 */

/* ── Config ──────────────────────────────────────────────── */
const API_BASE = "http://localhost:8006";

/* ── DOM refs ────────────────────────────────────────────── */
const messagesArea = document.getElementById("messagesArea");
const chatInput    = document.getElementById("chatInput");
const sendBtn      = document.getElementById("sendBtn");
const userSelect   = document.getElementById("userSelect");
const langSelect   = document.getElementById("langSelect");
const seedBtn      = document.getElementById("seedBtn");
const micBtn       = document.getElementById("micBtn");

/* ── State ───────────────────────────────────────────────── */
let isBotTyping = false;

/* ─────────────────────────────────────────────────────────── *
 *  INIT
 * ─────────────────────────────────────────────────────────── */
function init() {
  showWelcome();
  bindEvents();
  checkHealth();
}

function showWelcome() {
  const msgs = [
    "👋 Hi there! I'm your **FoodFlow Support Bot**.",
    "I can help you place orders, track them, cancel, refund, apply coupons, and more.",
    "Try the quick action buttons below or just type your question!",
  ];
  msgs.forEach((m, i) => {
    setTimeout(() => appendBotBubble(m, null), i * 400);
  });
}

/* ─────────────────────────────────────────────────────────── *
 *  EVENT BINDING
 * ─────────────────────────────────────────────────────────── */
function bindEvents() {
  sendBtn.addEventListener("click", handleSend);

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (chip.id === "chipCustomOrder") {
        const m = document.getElementById("orderModal");
        if(m) m.style.display = "block";
        return;
      }
      const msg = chip.getAttribute("data-msg");
      if (msg) sendMessage(msg);
    });
  });

  const modal = document.getElementById("orderModal");
  if (modal) {
    document.getElementById("closeModal").addEventListener("click", () => modal.style.display="none");
    window.addEventListener("click", (e) => { if (e.target == modal) modal.style.display="none"; });
    document.getElementById("modalAddItemBtn").addEventListener("click", () => {
      const row = document.createElement("div");
      row.className = "item-row";
      row.innerHTML = `<input type="text" class="i-name" placeholder="Item Name" value=""><input type="number" class="i-qty" placeholder="Qty" value="1" min="1" style="width: 60px;"><input type="number" class="i-price" placeholder="Price" value="50" min="1" style="width: 80px;">`;
      document.getElementById("modalItemsList").appendChild(row);
    });
    document.getElementById("modalSubmitBtn").addEventListener("click", () => {
      modal.style.display = "none";
      submitCustomOrder();
    });
  }

  seedBtn.addEventListener("click", handleSeedData);

  if (micBtn) {
    micBtn.addEventListener("click", handleVoiceInput);
  }
}

async function submitCustomOrder() {
  const items = [];
  document.querySelectorAll(".item-row").forEach(row => {
    const name = row.querySelector(".i-name").value.trim();
    if (name) {
      items.push({
        name,
        quantity: parseInt(row.querySelector(".i-qty").value) || 1,
        unit_price: parseFloat(row.querySelector(".i-price").value) || 0
      });
    }
  });

  if (items.length === 0) return;

  const body = {
    user_id: userSelect.value,
    restaurant_name: document.getElementById("modalRestaurant").value || "Custom Restaurant",
    payment_method: document.getElementById("modalPayment").value,
    delivery_address: document.getElementById("modalAddress").value || "Given Address",
    items
  };

  appendUserBubble(`Placed a custom order with ${items.length} item(s)`);
  const typingEl = showTyping();
  isBotTyping = true;
  sendBtn.disabled = true;

  try {
    let res;
    try {
      res = await fetch(`${API_BASE}/api/orders/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (e) {
      removeTyping(typingEl);
      renderBotResponse({ 
        type: "error", 
        source: "network", 
        message: "Unable to reach the server. Please try again." 
      });
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (e) {
      removeTyping(typingEl);
      renderBotResponse({ 
        type: "error", 
        source: "backend", 
        message: "Something went wrong while creating the order." 
      });
      return;
    }

    removeTyping(typingEl);

    // Explicitly handle FastAPI validation error arrays (422) if they aren't caught by the backend handler
    if (data.detail && !data.message) {
      const details = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : data.detail;
      renderBotResponse({
        type: "error",
        source: "backend",
        message: "Unable to create order. Please check the order details and try again.",
        data: { error_code: "ORDER_CREATE_FAILED", details }
      });
    } else if (!data.message) {
      // General fallback to ensure "undefined" never shows
      data.type = data.type || "error";
      data.message = "Something went wrong while creating the order.";
      renderBotResponse(data);
    } else {
      renderBotResponse(data);
    }

  } finally {
    isBotTyping = false;
    sendBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────── *
 *  SEND FLOW
 * ─────────────────────────────────────────────────────────── */
async function handleSend() {
  const text = chatInput.value.trim();
  if (!text || isBotTyping) return;
  chatInput.value = "";
  await sendMessage(text);
}

async function sendMessage(text) {
  appendUserBubble(text);
  const typingEl = showTyping();
  isBotTyping = true;
  sendBtn.disabled = true;

  try {
    const userId = userSelect.value;
    const lang = langSelect ? langSelect.value : "english";
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, message: text, language: lang }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    removeTyping(typingEl);
    renderBotResponse(data);

  } catch (err) {
    removeTyping(typingEl);
    appendBotBubble(
      "⚠️ Connection error — make sure the backend is running on `localhost:8000`.",
      "error"
    );
    console.error("[FoodFlow] API error:", err);
  } finally {
    isBotTyping = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

/* ─────────────────────────────────────────────────────────── *
 *  VOICE INPUT
 * ─────────────────────────────────────────────────────────── */
function handleVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    appendBotBubble("⚠️ Speech recognition is not supported in this browser.", "error");
    return;
  }
  
  if (micBtn.classList.contains("recording")) return;
  
  const recognition = new SpeechRecognition();
  const requestedLang = langSelect ? langSelect.value : "english";
  const langMap = { english: "en-US", hindi: "hi-IN", tamil: "ta-IN", spanish: "es-ES" };
  recognition.lang = langMap[requestedLang] || "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  
  recognition.onstart = () => {
    micBtn.classList.add("recording");
    chatInput.placeholder = "Listening...";
  };
  
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    chatInput.value = transcript;
    handleSend();
  };
  
  recognition.onerror = () => { chatInput.placeholder = "Ask about your order..."; };
  recognition.onend = () => {
    micBtn.classList.remove("recording");
    chatInput.placeholder = "Ask about your order, refunds, delivery…";
  };
  
  recognition.start();
}

/* ─────────────────────────────────────────────────────────── *
 *  RESPONSE RENDERER
 * ─────────────────────────────────────────────────────────── */
function renderBotResponse(resp) {
  switch (resp.type) {
    case "order_status":          renderOrderStatus(resp); break;
    case "order_history":         renderOrderHistory(resp); break;
    case "order_created":         renderOrderCreated(resp); break;
    case "reorder_created":       renderReorderCreated(resp); break;
    case "order_cancelled":       renderOrderCancelled(resp); break;
    case "ordered_items_history": renderOrderedItemsHistory(resp); break;
    case "refund_requested":      renderRefundRequested(resp); break;
    case "refund_status":         renderRefundStatus(resp); break;
    case "address_updated":       renderAddressUpdated(resp); break;
    case "rider_info":            renderRiderInfo(resp); break;
    case "support_ticket_created":renderTicketCreated(resp); break;
    case "coupon_result":         renderCouponResult(resp); break;
    case "delivery_estimate":     renderDeliveryEstimate(resp); break;
    case "faq":                   renderFAQ(resp); break;
    case "gemini":                renderGemini(resp); break;
    case "escalation":            renderEscalation(resp); break;
    case "error":
    default:
      renderError(resp);
  }
}

/* ── Specific Card Renderers ─────────────────────────────── */

function renderError(resp) {
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("error", "⚠️ ERROR"));
  
  // Strict guard against "undefined" or null messages
  let msg = resp.message;
  if (!msg || msg === "undefined") {
    msg = "An unexpected error occurred. Please try again.";
  }
  
  row.bubble.appendChild(makeText(msg));
  
  if (resp.data && resp.data.details) {
    const detailBox = document.createElement("div");
    detailBox.className = "error-details-box"; // Added class for easier styling if needed
    detailBox.style.marginTop = "8px";
    detailBox.style.fontSize = "0.8rem";
    detailBox.style.opacity = "0.8";
    detailBox.textContent = `Reason: ${resp.data.details}`;
    row.bubble.appendChild(detailBox);
  }
  
  appendRow(row.el);
}

function renderOrderStatus(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "📦 Order Status"));
  row.bubble.appendChild(makeText(message));
  if (data && data.order_id) row.bubble.appendChild(buildOrderCard(data));
  appendRow(row.el);
}

function renderOrderCreated(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "✅ Order Placed"));
  row.bubble.appendChild(makeText(message));
  if (data && data.order_id) row.bubble.appendChild(buildOrderCard(data));
  appendRow(row.el);
}

function renderReorderCreated(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "🔁 Reordered"));
  row.bubble.appendChild(makeText(message));
  if (data && data.order_id) row.bubble.appendChild(buildOrderCard(data));
  appendRow(row.el);
}

function renderOrderCancelled(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "❌ Cancelled"));
  row.bubble.appendChild(makeText(message));
  if (data && data.order_id) row.bubble.appendChild(buildOrderCard(data));
  appendRow(row.el);
}

function renderOrderedItemsHistory(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "🧾 Ordered Items"));
  row.bubble.appendChild(makeText(message));
  if (data && data.items && data.items.length > 0) {
    const itemsCard = document.createElement("div");
    itemsCard.className = "order-card highlight-card";
    let html = `<div style="font-weight:600; margin-bottom:8px;">${data.restaurant_name} - ${data.order_id}</div><div class="structured-items-list">`;
    data.items.forEach(i => {
      if (typeof i === "string") html += `<div class="sit-row"><span class="sit-name">${i}</span></div>`;
      else html += `<div class="sit-row"><span class="sit-name">${i.name}</span><span class="sit-qty">x${i.quantity}</span><span class="sit-price">₹${i.total_price || (i.quantity*i.unit_price)}</span></div>`;
    });
    html += `</div>`;
    if (data.total_amount) html += `<div style="text-align:right; margin-top:8px; font-weight:700;">Total: ₹${data.total_amount}</div>`;
    itemsCard.innerHTML = html;
    row.bubble.appendChild(itemsCard);
  }
  appendRow(row.el);
}

function renderRefundRequested(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "💸 Refund Request"));
  row.bubble.appendChild(makeText(message));
  if (data && data.order_id) {
    const card = document.createElement("div");
    card.className = "order-card highlight-card";
    card.innerHTML = `
      <div class="order-id">ORD: ${data.order_id}</div>
      <div style="font-weight:700; margin: 6px 0;">Amount: ₹${data.refund_amount}</div>
      <div style="font-size:0.78rem;color:var(--text-muted)">Status: ${data.refund_status} in ~${data.refund_eta_days} days.</div>
    `;
    row.bubble.appendChild(card);
  }
  appendRow(row.el);
}

function renderRefundStatus(resp) {
    const row = createBotRow();
    row.bubble.appendChild(makeBadge("firebase", "🔄 Refund Status"));
    row.bubble.appendChild(makeText(resp.message));
    appendRow(row.el);
}

function renderAddressUpdated(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "📍 Address Updated"));
  row.bubble.appendChild(makeText(message));
  if (data && data.delivery_address) {
    const card = document.createElement("div");
    card.className = "order-card highlight-card";
    card.innerHTML = `<div style="font-weight: 500; font-size: 0.85rem">New Address: ${data.delivery_address}</div>`;
    row.bubble.appendChild(card);
  }
  appendRow(row.el);
}

function renderRiderInfo(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "🏍️ Rider Info"));
  row.bubble.appendChild(makeText(message));
  if (data && data.rider_name) {
    const ri = document.createElement("div");
    ri.className = "rider-info";
    ri.innerHTML = `
      <div class="rider-avatar">🏍️</div>
      <div>
        <div class="rider-name">🧑 ${data.rider_name}</div>
        ${data.rider_phone ? `<div class="rider-phone">📱 ${data.rider_phone}</div>` : ''}
      </div>
      ${data.estimated_arrival_minutes ? `<div class="rider-eta">⏱ ${data.estimated_arrival_minutes} min</div>` : ''}
    `;
    row.bubble.appendChild(ri);
  }
  appendRow(row.el);
}

function renderTicketCreated(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "🎫 Support Ticket"));
  row.bubble.appendChild(makeText(message));
  if (data && data.ticket_id) {
    const card = document.createElement("div");
    card.className = "order-card"; 
    card.innerHTML = `
      <div class="order-id">TICKET: ${data.ticket_id}</div>
      <div style="font-weight:700; margin: 6px 0;">Issue: ${data.issue_type.replace('_', ' ').toUpperCase()}</div>
      <div style="font-size:0.78rem;color:var(--text-muted)">${data.description}</div>
      <div class="order-status-pill status-preparing" style="display:inline-block;margin-top:8px;">Status: ${data.status}</div>
    `;
    row.bubble.appendChild(card);
  }
  appendRow(row.el);
}

function renderCouponResult(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "🎫 Coupon"));
  row.bubble.appendChild(makeText(message));
  if (data && data.details) {
    const card = document.createElement("div");
    card.className = "order-card highlight-card"; 
    card.innerHTML = `
      <div style="font-weight:700;">Code: ${data.coupon}</div>
      <div style="font-size:0.8rem;color:var(--text-muted)">Type: ${data.details.type}</div>
      <div style="font-size:0.8rem;color:var(--text-muted)">Discount: ${data.details.discount}${data.details.type==='percentage'?'%':' flat'}</div>
    `;
    row.bubble.appendChild(card);
  }
  appendRow(row.el);
}

function renderDeliveryEstimate(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("faq", "🛵 Delivery Estimate"));
  row.bubble.appendChild(makeText(message));
  if (data) {
    const card = document.createElement("div");
    card.className = "order-card"; 
    card.innerHTML = `
      <div style="font-size:0.8rem;">Base Fee: ₹${data.base_fee}</div>
      <div style="font-size:0.8rem;">Per Km: ₹${data.per_km}</div>
    `;
    row.bubble.appendChild(card);
  }
  appendRow(row.el);
}


function renderOrderHistory(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("firebase", "📦 History"));
  row.bubble.appendChild(makeText(message));

  if (data && data.orders && data.orders.length) {
    const hc = document.createElement("div");
    hc.className = "history-card";
    data.orders.forEach((o) => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <div class="history-icon">${restaurantEmoji(o.restaurant_name)}</div>
        <div class="history-info">
          <div class="history-restaurant">${o.restaurant_name}</div>
          <div class="history-items-text">${(o.items || []).map(i => typeof i === "string" ? i : i.name).join(", ")}</div>
        </div>
        <div class="history-right">
          <div class="history-amount">₹${o.total_amount}</div>
          <div class="history-status ${statusClass(o.status)}" style="padding:2px 6px;border-radius:20px;font-size:0.65rem">${o.status}</div>
        </div>
      `;
      hc.appendChild(item);
    });
    row.bubble.appendChild(hc);
  } else {
    row.bubble.appendChild(makeText("No past orders found. Start ordering now!"));
  }
  appendRow(row.el);
}

function renderFAQ(resp) {
  const { data, message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("faq", "📚 FAQ Match"));
  if (data && data.matched_question) {
    const fc = document.createElement("div");
    fc.className = "faq-card";
    fc.innerHTML = `<div class="faq-q">Q: ${data.matched_question}</div>${escHtml(message)}`;
    row.bubble.appendChild(fc);
  } else {
    row.bubble.appendChild(makeText(message));
  }
  appendRow(row.el);
}

function renderGemini(resp) {
  const { message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("gemini", "🤖 AI-Assisted"));
  const gc = document.createElement("div");
  gc.className = "gemini-card";
  gc.innerHTML = `
    ${escHtml(message)}
    <div class="gemini-footer">
      <span>✨</span> Generated by Gemini AI · Always verify order details in the app
    </div>
  `;
  row.bubble.appendChild(gc);
  appendRow(row.el);
}

function renderEscalation(resp) {
  const { message } = resp;
  const row = createBotRow();
  row.bubble.appendChild(makeBadge("error", "🚨 Live Escalation"));
  const ec = document.createElement("div");
  ec.className = "escalation-card";
  ec.innerHTML = `
    <div class="escalation-msg">${escHtml(message)}</div>
    <div class="spinner-container">
      <div class="escalation-spinner"></div>
      <span>Routing to Live Support Team...</span>
    </div>
  `;
  row.bubble.appendChild(ec);
  appendRow(row.el);
}

/* ─────────────────────────────────────────────────────────── *
 *  CARDS & BUBBLES
 * ─────────────────────────────────────────────────────────── */

function buildOrderCard(data) {
    const card = document.createElement("div");
    card.className = "order-card";

    const hdr = document.createElement("div");
    hdr.className = "order-card-header";
    hdr.innerHTML = `
      <span class="order-id">${data.order_id}</span>
      <span class="order-status-pill ${statusClass(data.status)}">${data.status}</span>
    `;
    card.appendChild(hdr);

    const rest = document.createElement("div");
    rest.className = "order-restaurant";
    rest.textContent = data.restaurant_name || "Restaurant";
    card.appendChild(rest);

    if (data.items && data.items.length) {
      const itemsContainer = document.createElement("div");
      itemsContainer.className = "structured-items-list";
      let stringItems = [];
      data.items.forEach(i => {
        if (typeof i === "string") { stringItems.push(i); return; }
        const row = document.createElement("div");
        row.className = "sit-row";
        row.innerHTML = `<span class="sit-name">${i.quantity}x ${i.name}</span><span class="sit-price">₹${i.total_price || (i.quantity*i.unit_price)}</span>`;
        itemsContainer.appendChild(row);
      });
      if (stringItems.length > 0) {
        itemsContainer.innerHTML = `<div style="font-size: 0.85rem; color: var(--text-muted)">${stringItems.join(" • ")}</div>`;
      }
      card.appendChild(itemsContainer);
    }

    const meta = document.createElement("div");
    meta.className = "order-meta";
    if (data.total_amount)    meta.innerHTML += `<span>💰 ₹${data.total_amount}</span>`;
    if (data.payment_method)  meta.innerHTML += `<span>💳 ${data.payment_method}</span>`;
    if (data.delivery_stage)  meta.innerHTML += `<span>📍 ${data.delivery_stage}</span>`;
    card.appendChild(meta);

    card.appendChild(makeTimeline(data.status, data.delivery_stage));

    if (data.rider_name) {
      const ri = document.createElement("div");
      ri.className = "rider-info";
      ri.innerHTML = `
        <div class="rider-avatar">🏍️</div>
        <div>
          <div class="rider-name">🧑 ${data.rider_name}</div>
          ${data.rider_phone ? `<div class="rider-phone">📱 ${data.rider_phone}</div>` : ''}
        </div>
        ${data.estimated_arrival_minutes ? `<div class="rider-eta">⏱ ${data.estimated_arrival_minutes} min</div>` : ''}
      `;
      card.appendChild(ri);
    }
    return card;
}

function createBotRow() {
  const el = document.createElement("div");
  el.className = "msg-row bot-row";
  const av = document.createElement("div");
  av.className = "avatar bot";
  av.textContent = "🍔";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot";
  el.appendChild(av);
  el.appendChild(bubble);
  return { el, bubble };
}

function appendBotBubble(text, type) {
  const row = createBotRow();
  if (type) row.bubble.appendChild(makeBadge(type, badgeLabel(type)));
  row.bubble.appendChild(makeText(text));
  appendRow(row.el);
}

function appendUserBubble(text) {
  const el = document.createElement("div");
  el.className = "msg-row user";
  const av = document.createElement("div");
  av.className = "avatar user-av";
  av.textContent = "👤";
  const bubble = document.createElement("div");
  bubble.className = "bubble user";
  bubble.textContent = text;
  el.appendChild(av);
  el.appendChild(bubble);
  appendRow(el);
}

function appendRow(el) {
  messagesArea.appendChild(el);
  scrollToBottom();
}

function makeText(raw) {
  const p = document.createElement("p");
  p.innerHTML = escHtml(raw).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  return p;
}

function makeBadge(type, label) {
  const b = document.createElement("div");
  b.className = `source-badge badge-${type}`;
  b.textContent = label;
  return b;
}

function badgeLabel(type) {
  const map = { faq: "📚 FAQ", firebase: "📦 Firebase", gemini: "🤖 AI", error: "⚠️ Error" };
  return map[type] || type;
}

function escHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ─────────────────────────────────────────────────────────── *
 *  TYPING INDICATOR
 * ─────────────────────────────────────────────────────────── */
function showTyping() {
  const el = document.createElement("div");
  el.className = "msg-row typing-indicator";
  el.id = "typingIndicator";
  el.innerHTML = `
    <div class="avatar bot">🍔</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
  `;
  messagesArea.appendChild(el);
  scrollToBottom();
  return el;
}

function removeTyping(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

/* ─────────────────────────────────────────────────────────── *
 *  DELIVERY TIMELINE
 * ─────────────────────────────────────────────────────────── */
const TIMELINE_STAGES = [
  { key: "placed",    label: "Placed",    icon: "🛒" },
  { key: "confirmed", label: "Confirmed", icon: "✅" },
  { key: "preparing", label: "Preparing", icon: "👨‍🍳" },
  { key: "picked",    label: "Picked Up", icon: "🏍️" },
  { key: "on-way",    label: "On the Way",icon: "🛵" },
  { key: "delivered", label: "Delivered", icon: "🎉" },
];

function statusToStageIndex(status, stage) {
  const combined = `${(status || "").toLowerCase()} ${(stage || "").toLowerCase()}`;
  if (combined.includes("deliver")) return 5;
  if (combined.includes("on the way") || combined.includes("nearby")) return 4;
  if (combined.includes("picked") || combined.includes("rider")) return 3;
  if (combined.includes("prepar") || combined.includes("cooking")) return 2;
  if (combined.includes("confirm")) return 1;
  if (combined.includes("cancel") || combined.includes("refund")) return -1;
  return 0;
}

function makeTimeline(status, stage) {
  const container = document.createElement("div");
  container.className = "delivery-timeline";

  const activeIdx = statusToStageIndex(status, stage);
  if (activeIdx === -1) {
    const note = document.createElement("div");
    note.style.fontSize = "0.78rem";
    note.style.color = "var(--tag-error)";
    note.textContent = `🚫 ${status}`;
    container.appendChild(note);
    return container;
  }

  TIMELINE_STAGES.forEach((s, i) => {
    const step = document.createElement("div");
    let cls = "timeline-step";
    if (i < activeIdx)  cls += " done";
    if (i === activeIdx) cls += " active";
    step.className = cls;

    step.innerHTML = `
      <div class="ts-dot">${i <= activeIdx ? s.icon : ""}</div>
      <div class="ts-label">${s.label}</div>
    `;
    container.appendChild(step);
  });
  return container;
}

/* ─────────────────────────────────────────────────────────── *
 *  UTILITIES
 * ─────────────────────────────────────────────────────────── */
function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("on the way") || s.includes("transit")) return "status-on-way";
  if (s.includes("deliver"))   return "status-delivered";
  if (s.includes("prepar") || s.includes("cooking")) return "status-preparing";
  if (s.includes("cancel"))    return "status-cancelled";
  if (s.includes("refund"))    return "status-refunded";
  if (s.includes("pick"))      return "status-picked-up";
  return "";
}

function restaurantEmoji(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("burger") || n.includes("hub")) return "🍔";
  if (n.includes("pizza")) return "🍕";
  if (n.includes("biryani")) return "🍚";
  if (n.includes("sushi")) return "🍱";
  if (n.includes("dosa") || n.includes("delight")) return "🫓";
  if (n.includes("wok") || n.includes("chinese")) return "🍜";
  if (n.includes("taco") || n.includes("fiesta")) return "🌮";
  if (n.includes("kebab") || n.includes("king")) return "🍢";
  if (n.includes("pancake") || n.includes("waffle")) return "🥞";
  if (n.includes("thali")) return "🍽️";
  if (n.includes("healthy") || n.includes("bowl")) return "🥗";
  if (n.includes("roll")) return "🫔";
  return "🍴";
}

function scrollToBottom() {
  requestAnimationFrame(() => { messagesArea.scrollTop = messagesArea.scrollHeight; });
}

/* ─────────────────────────────────────────────────────────── *
 *  SEED DATA HANDLER
 * ─────────────────────────────────────────────────────────── */
async function handleSeedData() {
  seedBtn.disabled = true;
  seedBtn.textContent = "⏳ Seeding…";

  try {
    const res = await fetch(`${API_BASE}/api/seed-data`, { method: "POST" });
    const data = await res.json();
    if (res.ok && data.success) {
      appendBotBubble(`✅ Demo data seeded! ${data.users_seeded} users & ${data.orders_seeded} orders created in Firebase.`, "firebase");
    } else {
      appendBotBubble(`⚠️ Seed failed: ${data.detail || data.error || "Firebase may not be configured."}`, "error");
    }
  } catch (err) {
    appendBotBubble("⚠️ Seed request failed — is the backend running?", "error");
  } finally {
    seedBtn.disabled = false;
    seedBtn.textContent = "🌱 Seed Data";
  }
}

/* ─────────────────────────────────────────────────────────── *
 *  HEALTH CHECK (updates status dot)
 * ─────────────────────────────────────────────────────────── */
async function checkHealth() {
  const dot   = document.getElementById("statusDot");
  const label = document.getElementById("statusLabel");

  try {
    const res  = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      const data = await res.json();
      dot.style.background   = "#3DDC84";
      dot.style.boxShadow    = "0 0 10px rgba(61,220,132,0.7)";
      label.style.color      = "#3DDC84";
      label.textContent      = "Online";

      const notices = [];
      if (!data.firebase_available) notices.push("⚠️ Firebase not configured.");
      if (!data.gemini_available)   notices.push("ℹ️ Gemini API not configured.");
      notices.forEach((n, i) => setTimeout(() => appendBotBubble(n, "error"), 1600 + i * 600));
    } else { setBotOffline(dot, label); }
  } catch { setBotOffline(dot, label); }
}

function setBotOffline(dot, label) {
  dot.style.background  = "#FF4D6D";
  dot.style.boxShadow   = "0 0 10px rgba(255,77,109,0.7)";
  label.style.color     = "#FF4D6D";
  label.textContent     = "Offline";
}

document.addEventListener("DOMContentLoaded", init);
