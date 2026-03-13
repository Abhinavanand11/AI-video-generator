# 🎬 AI Video Generator

This project generates short AI videos from a topic using **FastAPI (backend)** and a **simple frontend UI**.

---

# 🔑 OpenAI API Key

1. Create an API key from the OpenAI dashboard.
2. Copy the key.

---

# ⚙️ Environment Variables

Create a `.env` file inside the **backend** folder.

---

# 🧠 Backend Setup

### 1. Navigate to the backend folder


cd backend

2. Install dependencies
pip install -r requirements.txt

4. Run the FastAPI server
uvicorn main:app --reload --port 8000

Backend will run at:

http://localhost:8000

#🎨 Frontend Setup

navigate to the frontend folder.

cd frontend

Start a simple local server:

python -m http.server 3000
