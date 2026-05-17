# MissionLog Architecture & Blueprint

## The Big Picture
MissionLog is a **decoupled, single-page application (SPA)** integrated into the webNexus Django project.

- **Backend (Django):** Headless API provider. Handles database, authentication, and logic.
- **Frontend (Vue 3 + Vite):** Reactive UI. Handles user interactions and data presentation.

## Architectural Mechanics

### 1. Separation of Concerns
- Django code lives in `/missionlog/`.
- Vue code lives in `/frontend-missionlog/`.
- Communication happens via a clean JSON API.

### 2. Development Workflow (Dual-Server)
- **Django Server:** `python manage.py runserver` (Port 8000).
- **Vite Server:** `npm run dev` (Port 5173).
- **Proxy:** Vite is configured to proxy `/api/` requests to Django during development to avoid CORS issues.

### 3. Production Pipeline (The Bridge)
- **Build:** `npm run build` generates optimized assets in `/frontend-missionlog/dist/`.
- **Serving:** Django is configured to serve `index.html` from the `dist/` folder and include it in `STATICFILES_DIRS`.
- **Deployment:** The `dist/` folder is committed to Git for a simple `git pull` deployment on the server.

## Rules of Engagement

### Rule A: Pure JSON Payloads
All data exchange between Vue and Django must use standard JSON.
- `GET`: Fetch data.
- `POST`/`PUT`/`DELETE`: Modify data.

### Rule B: Seamless Session Auth
The SPA inherits the logged-in user session from Django automatically. No complex token setups are required.

### Rule C: Bulletproof CSRF Protection
Vue is configured to read the `csrftoken` cookie set by Django and attach it to the `X-CSRFToken` header for all state-changing requests.

---
*Created on Sunday, May 17, 2026*
