/**
 * FoodFlow Support Bot — script.js
 * Handles chat logic, API calls, and dynamic card rendering.
 * Vanilla JS only — no frameworks.
 */

/* ── Config ──────────────────────────────────────────────── */
// Change to 8000 after stopping any old server; currently 9000 is fresh
const API_BASE = "http://localhost:8000";

/* ── DOM refs ────────────────────────────────────────────── */
const messagesArea = document.getElementById("messagesArea");
const chatInput    = document.getElementById("chatInput");
const sendBtn      = document.getElementById("sendBtn");
const userSelect   = document.getElementById("userSelect");
const seedBtn      = document.getElementById("seedBtn");

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
    "I can help you track orders, check your order history, answer delivery questions, and more.",
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
  // Send on button click
  sendBtn.addEventListener("click", handleSend);

  // Enter to send (shift+enter = newline in textarea — here is input, so just enter)
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Quick chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const msg = chip.getAttribute("data-msg");
      if (msg) sendMessage(msg);
    });
  });

  // Seed button
  seedBtn.addEventListener("click", handleSeedData);
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
  // Render user bubble
  appendUserBubble(text);

  // Show typing indicator
  const typingEl = showTyping();
  isBotTyping = true;
  sendBtn.disabled = true;

  try {
    const userId = userSelect.value;
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, message: text }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

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
 *  RESPONSE RENDERER (routes by type)
 * ─────────────────────────────────────────────────────────── */
function renderBotResponse(resp) {
  switch (resp.type) {
    case "order_status":
      renderOrderStatus(resp);
      break;
    case "order_history":
      renderOrderHistory(resp);
      break;
    case "faq":
      renderFAQ(resp);
      break;
    case "gemini":
      renderGemini(resp);
      break;
    case "error":
    default:
      appendBotBubble(`⚠️ ${resp.message}`, "error");
  }
}

/* ── Order Status Card ────────────────────────────────────── */
function renderOrderStatus(resp) {
  const { data, message } = resp;
  const row = createBotRow();

  // Badge
  row.bubble.appendChild(makeBadge("firebase", "📦 Firebase"));

  // Text
  row.bubble.appendChild(makeText(message));

  // Card
  if (data && data.order_id) {
    const card = document.createElement("div");
    card.className = "order-card";

    // Header
    const hdr = document.createElement("div");
    hdr.className = "order-card-header";
    hdr.innerHTML = `
      <span class="order-id">${data.order_id}</span>
      <span class="order-status-pill ${statusClass(data.status)}">${data.status}</span>
    `;
    card.appendChild(hdr);

    // Restaurant
    const rest = document.createElement("div");
    rest.className = "order-restaurant";
    rest.textContent = data.restaurant_name || "Restaurant";
    card.appendChild(rest);

    // Items
    if (data.items && data.items.length) {
      const items = document.createElement("div");
      items.className = "order-items";
      items.textContent = data.items.join(" • ");
      card.appendChild(items);
    }

    // Meta
    const meta = document.createElement("div");
    meta.className = "order-meta";
    if (data.total_amount)    meta.innerHTML += `<span>💰 ₹${data.total_amount}</span>`;
    if (data.payment_method)  meta.innerHTML += `<span>💳 ${data.payment_method}</span>`;
    if (data.delivery_stage)  meta.innerHTML += `<span>📍 ${data.delivery_stage}</span>`;
    card.appendChild(meta);

    // Timeline
    card.appendChild(makeTimeline(data.status, data.delivery_stage));

    // Rider info
    if (data.rider_name) {
      const ri = document.createElement("div");
      ri.className = "rider-info";
      ri.innerHTML = `
        <div class="rider-avatar">🏍️</div>
        <div>
          <div class="rider-name">🧑 ${data.rider_name}</div>
          ${data.rider_phone ? `<div class="rider-phone">📱 ${data.rider_phone}</div>` : ''}
        </div>
        ${data.eta ? `<div class="rider-eta">⏱ ${data.eta} min</div>` : ''}
      `;
      card.appendChild(ri);
    }

    row.bubble.appendChild(card);
  }

  appendRow(row.el);
}

/* ── Order History Card───────────────────────────────────── */
function renderOrderHistory(resp) {
  const { data, message } = resp;
  const row = createBotRow();

  row.bubble.appendChild(makeBadge("firebase", "📦 Firebase"));
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
          <div class="history-items-text">${(o.items || []).join(", ")}</div>
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
    row.bubble.appendChild(
      makeText("No past orders found. Start ordering now!")
    );
  }

  appendRow(row.el);
}

/* ── FAQ Card ────────────────────────────────────────────── */
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

/* ── Gemini Card ─────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────── *
 *  BUBBLE HELPERS
 * ─────────────────────────────────────────────────────────── */
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
  // Minimal markdown: **bold**
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
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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
    <div class="typing-dots">
      <span></span><span></span><span></span>
    </div>
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
  if (n.includes("burger") || n.includes("hub"))    return "🍔";
  if (n.includes("pizza"))                           return "🍕";
  if (n.includes("biryani"))                         return "🍚";
  if (n.includes("sushi"))                           return "🍱";
  if (n.includes("dosa") || n.includes("delight"))  return "🫓";
  if (n.includes("wok") || n.includes("chinese"))   return "🍜";
  if (n.includes("taco") || n.includes("fiesta"))   return "🌮";
  if (n.includes("kebab") || n.includes("king"))    return "🍢";
  if (n.includes("pancake") || n.includes("waffle"))return "🥞";
  if (n.includes("thali"))                           return "🍽️";
  if (n.includes("healthy") || n.includes("bowl"))  return "🥗";
  if (n.includes("roll"))                            return "🫔";
  return "🍴";
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  });
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
      appendBotBubble(
        `✅ Demo data seeded! ${data.users_seeded} users & ${data.orders_seeded} orders created in Firebase.`,
        "firebase"
      );
    } else {
      appendBotBubble(
        `⚠️ Seed failed: ${data.detail || data.error || "Firebase may not be configured."}`,
        "error"
      );
    }
  } catch (err) {
    appendBotBubble(
      "⚠️ Seed request failed — is the backend running?",
      "error"
    );
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

      // Optionally notify about Firebase / Gemini state
      const notices = [];
      if (!data.firebase_available) notices.push("⚠️ Firebase not configured — order queries will be unavailable.");
      if (!data.gemini_available)   notices.push("ℹ️ Gemini API not configured — AI fallback disabled.");
      notices.forEach((n, i) => setTimeout(() => appendBotBubble(n, "error"), 1600 + i * 600));
    } else {
      setBotOffline(dot, label);
    }
  } catch {
    setBotOffline(dot, label);
  }
}

function setBotOffline(dot, label) {
  dot.style.background  = "#FF4D6D";
  dot.style.boxShadow   = "0 0 10px rgba(255,77,109,0.7)";
  label.style.color     = "#FF4D6D";
  label.textContent     = "Offline";
}

/* ── Kick off ─────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", init);
