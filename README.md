# 🍔 FoodFlow Support Bot

> AI-powered food delivery customer support chatbot — built for hackathon Round 1.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Firebase](https://img.shields.io/badge/Firebase-Firestore-FF6F00?style=flat-square&logo=firebase)](https://firebase.google.com)
[![Gemini](https://img.shields.io/badge/Google-Gemini_AI-4285F4?style=flat-square&logo=google)](https://ai.google.dev)

---

## 📋 Project Overview

FoodFlow Support Bot is a full-stack chatbot inspired by Swiggy/Zomato support flows. It handles:
- **Real-time order tracking** via Firebase Firestore
- **Instant FAQ answers** via an intelligent matching engine (115+ entries)
- **AI-assisted fallback** via Google Gemini when neither Firebase nor FAQ can answer

---

## ✨ Feature List

| Feature | Description |
|---|---|
| 🛵 Order Tracking | Real-time order status from Firestore |
| 📦 Order History | Past orders with restaurant, items, amount |
| 📚 FAQ Engine | 115+ entries, multi-strategy matching |
| 🤖 Gemini Fallback | AI-generated support responses |
| 🌱 Data Seeder | One-click demo data creation |
| 🎯 Intent Detection | Regex-based order intent routing |
| 🏷️ Source Badges | FAQ / Firebase / AI labels in UI |
| 📱 Mobile-Responsive | Works perfectly on all screen sizes |
| ⚡ Graceful Degradation | Works even without Firebase or Gemini |

---

## 🏗️ Architecture Flow

```
User Message
      │
      ▼
┌─────────────────────────┐
│   Intent Detection      │  ← regex patterns on the message
└─────────────┬───────────┘
              │ order intent?
     ┌────────┴────────┐
     │ YES             │ NO
     ▼                 ▼
┌─────────┐    ┌──────────────┐
│Firebase │    │  FAQ Engine  │  ← multi-strategy matching
│Firestore│    │(115+ entries)│
└─────────┘    └──────┬───────┘
                      │ no match?
                      ▼
               ┌─────────────┐
               │ Gemini API  │  ← only as last resort
               └─────────────┘
```

---

## 📁 Folder Structure

```
hackathon/
├── frontend/
│   ├── index.html          ← Chatbot UI
│   ├── style.css           ← Dark glassmorphism design
│   └── script.js           ← Chat logic & rendering
│
├── backend/
│   ├── main.py             ← FastAPI app + all routes
│   ├── models/
│   │   └── schemas.py      ← Pydantic models
│   ├── services/
│   │   ├── faq_service.py      ← FAQ matching engine
│   │   ├── firebase_service.py ← Firestore queries + seed
│   │   └── gemini_service.py   ← Gemini API wrapper
│   ├── data/
│   │   └── faq_data.json   ← 115+ FAQ entries
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

---

## 🚀 Local Setup

### 1. Clone & enter the project

```bash
cd /path/to/hackathon
```

### 2. Set up Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Configure environment variables

```bash
cp backend/.env.example backend/.env
# Then edit backend/.env with your actual keys
```

### 5. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 6. Open the frontend

Open `frontend/index.html` directly in your browser — no build step needed.

Or serve it with Python:
```bash
cd frontend
python3 -m http.server 3000
# Then open http://localhost:3000
```

---

## 🔥 Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a project (e.g., `foodflow-bot`)
3. Enable **Cloud Firestore** in Native mode
4. Go to **Project Settings → Service Accounts → Generate new private key**
5. Download the JSON file and save it as `backend/firebase-service-account.json`
6. Set the path in your `.env`:

```env
FIREBASE_SERVICE_ACCOUNT_PATH=backend/firebase-service-account.json
```

7. Seed demo data by clicking **🌱 Seed Data** in the UI or:
```bash
curl -X POST http://localhost:8000/api/seed-data
```

> **No Firebase?** The bot still works — FAQ and Gemini responses are unaffected.

---

## 🤖 Gemini API Setup

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create an API key
3. Add it to your `.env`:

```env
GEMINI_API_KEY=your_actual_key_here
```

> **No Gemini key?** The bot still works — it returns a polite "unable to answer" message instead of crashing.

---

## 🧠 FAQ-First Routing Explained

The FAQ engine uses 4-strategy matching in order of priority:

| Priority | Strategy | Score |
|---|---|---|
| 1 | Exact question match | 1.00 |
| 2 | Substring match (question or alias) | 0.85–0.95 |
| 3 | Exact alias match | 0.95 |
| 4 | Keyword overlap (Jaccard F1) | 0.0–0.80 |

A match is only returned if the **confidence ≥ 0.35** (configurable in `faq_service.py`).

---

## 📡 API Reference

### `GET /api/health`
```json
{
  "status": "ok",
  "firebase_available": true,
  "gemini_available": true
}
```

### `POST /api/chat`
**Request:**
```json
{ "user_id": "user_001", "message": "Where is my order?" }
```
**Response:**
```json
{
  "type": "order_status",
  "source": "firebase",
  "message": "Your order is currently on the way.",
  "data": { "order_id": "ORD1001", "eta": 12, ... }
}
```

### `POST /api/seed-data`
Seeds 3 users + 12 realistic orders into Firestore.

### `GET /api/orders/{user_id}`
Returns all orders for a user.

### `GET /api/orders/{user_id}/active`
Returns the current active order.

### `GET /api/debug/faq-match?query=...`
Returns FAQ matching debug info — scores for all candidates.
```bash
curl "http://localhost:8000/api/debug/faq-match?query=refund+policy"
```

---

## 🎬 Hackathon Demo Flow

1. Open `frontend/index.html`
2. Click **🌱 Seed Data** (creates Firebase demo data)
3. Send: `"Track my order"` → See Firebase order status card
4. Send: `"Show my order history"` → See order history timeline
5. Send: `"What payment methods are accepted?"` → See FAQ card
6. Switch to **user_002** → Send `"Where is my order?"`
7. Send: `"Tell me about surge pricing"` → See Gemini fallback response

---

## 🔮 Future Improvements

- [ ] WebSocket for real-time order push updates
- [ ] Multi-language support (Hindi, Tamil, etc.)
- [ ] Voice input integration
- [ ] Order rating flow in chatbot
- [ ] Rider location map embed
- [ ] Backend conversation history with session IDs
- [ ] Sentiment analysis to detect frustrated users
- [ ] Admin dashboard for FAQ management
- [ ] WhatsApp / Telegram bot integration

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | Firebase Firestore |
| AI | Google Gemini 1.5 Flash |
| Config | python-dotenv |
| Models | Pydantic v2 |

---

*Built with ❤️ for hackathon Round 1*
