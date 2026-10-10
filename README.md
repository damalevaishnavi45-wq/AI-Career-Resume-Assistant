# AI Career & Resume Assistant

## Project Overview

AI Career & Resume Assistant is a student-level web application that helps users (students and early-career job seekers) upload resumes, get a simple AI-driven analysis, find skill-based job matches, practice interview questions, and receive beginner-friendly career guidance.

This implementation uses Django as the backend and Google Gemini (via the `google-genai` SDK) for AI-powered resume analysis, interview preparation and career guidance.

## Problem Statement

Many students struggle to convert academic projects and course work into effective resumes, identify skill gaps, and prepare for interviews. This project provides structured, beginner-friendly feedback and guidance to help students present themselves better and practise interview questions tailored to common entry-level roles.

## Objectives

- Provide a simple, secure interface for users to upload a resume (PDF)
- Extract readable text from uploaded resumes and analyze it with an LLM
- Show a resume score, detected skills and suggested improvements
- Match resumes to simple job-role templates based on skills
- Generate interview questions and career guidance tailored to the user's profile

## Key Features

- **User Registration / Login / Logout** — basic Django authentication.
- **Resume PDF Upload** — upload a PDF resume saved to `media/resumes/`.
- **Resume Analysis using Google Gemini** — structured JSON analysis (summary, skills, strengths, gaps, score).
- **Resume Score and feedback** — a simple numeric score and textual guidance.
- **Skills, skill gaps, strengths and improvements** — parsed and presented in the UI.
- **Job Matching** — a skill-based matching algorithm implemented in `career/job_matching.py`.
- **Interview Preparation using Google Gemini** — generates beginner-friendly interview questions in JSON and displays them.
- **Career Guidance using Google Gemini** — structured suggestions and next steps for a student's career goals.

## Technologies Used

- Python
- Django
- HTML, CSS, JavaScript
- Bootstrap (used in templates)
- Google Gemini API (`google-genai`) — used server-side through the `career/ai_service.py` wrapper
- `python-dotenv` for loading `.env`
- `pypdf` for PDF text extraction
- SQLite (project includes `db.sqlite3`)

Note: The project templates are server-rendered Django templates. React and Vite were listed as possible frontend technologies but this repository does not include a React/Vite app (no `package.json` or `src/` present). The README therefore reflects what is implemented.

## System Workflow

Simple flow:

User → Login → Dashboard → Select Feature (Resume Analysis / Job Matching / Interview Prep / Career Guidance) → Resume / Input → Processing (local parsing + Gemini calls) → Result (displayed on page)

## Project Structure (important files & folders)

- `manage.py` — Django management entrypoint
- `requirements.txt` — Python dependencies used for the project
- `db.sqlite3` — project SQLite database (development)
- `.env` — environment variables (contains `GEMINI_API_KEY`; do not commit or expose this file)
- `backend/` — Django project settings and WSGI/ASGI
  - `backend/settings.py`
  - `backend/urls.py`
- `career/` — main Django app
  - `career/views.py` — view functions for upload, analysis, interview prep, career guidance
  - `career/ai_service.py` — wrapper for Google Gemini (`google-genai`) calls and retry logic
  - `career/resume_parser.py` — PDF extraction (uses `pypdf` lazily)
  - `career/job_matching.py` — skill-based matching helper
  - `career/models.py` — `Resume` model
  - `career/forms.py` — upload form
  - `career/urls.py`
  - `career/tests.py` — some unit tests for forms and job matching
- `templates/` — Django templates
  - `home.html`, `upload_resume.html`, `resume_result.html`, `interview_prep.html`, `career_guidance.html`, `login.html`, `register.html`, `base.html`
- `static/css/styles.css` — shared stylesheet
- `media/resumes/` — uploaded resumes directory (runtime)

Do not modify the project structure when running the application.

## Gemini API Integration

The app uses Google Gemini via the `google-genai` Python SDK. Gemini is used for:

- Resume Analysis (`analyze_resume_text` in `career/ai_service.py`)
- Interview Preparation (`generate_interview_questions` in `career/ai_service.py`)
- Career Guidance (`generate_career_guidance` in `career/ai_service.py`)

The implementation loads the API key from `.env` (the `GEMINI_API_KEY` environment variable). The code includes conservative retry logic for transient server errors (three attempts with a short delay). This README does not include or reveal the API key.

## Job Matching

Job matching is a simple, deterministic, skill-based matcher implemented in `career/job_matching.py`. It uses the skills detected in the resume analysis to score and suggest likely entry-level job roles. This is not a machine-learning model — it is a rule-based matching approach suitable for demonstration.

## Authentication

The project uses Django's built-in authentication for user registration, login and logout. Views providing the main features are protected with `@login_required`.

## Installation and Setup (Windows)

1. Clone the repository and open a terminal in the project root.
2. Create and activate a virtual environment (the project was developed with a `venv`):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
# If you plan to call Gemini, also install google-genai in the same venv:
python -m pip install google-genai
```

4. Ensure `.env` exists at the project root and contains `GEMINI_API_KEY` (do not commit this file):

```
GEMINI_API_KEY=your_api_key_here
```

## Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key used by `google-genai`. Do NOT expose this key in source control, logs, or public places.

## How to Run the Project

1. Activate the virtual environment (see steps above).
2. Apply migrations (if needed):

```powershell
python manage.py migrate
```

3. Run the development server:

```powershell
python manage.py runserver
```

4. Open `http://127.0.0.1:8000/` in your browser, register or login, and use the dashboard to access features.

## Testing

Functional tests performed during development:

- Login / Register / Logout: tested successfully
- Resume Analysis: tested successfully
- Job Matching: tested successfully
- Interview Preparation: tested successfully (Gemini generation verified)
- Career Guidance: tested successfully (Gemini generation verified)
- Gemini generation tested during functional runs; final functional tests reported no application errors
- Gemini API cost during testing: ₹0 (no paid usage beyond free/testing limits)

## Limitations

- This is a student project and not production-hardened. Notable limitations:
  - Resume parsing depends on text-based PDFs; scanned images without OCR may not parse correctly.
  - The job-matching logic is rule-based and simple — it is not a production recommender system.
  - The app stores uploaded resumes locally under `media/` and uses SQLite by default; this is suitable for demos only.
  - Gemini calls depend on external API availability and may incur costs if used beyond free tiers.

## Future Scope

- Add OCR support for scanned resumes.
- Associate uploaded resumes with `auth.User` records and add resume management UI.
- Improve job matching with a data-driven model or configurable role templates.
- Add more unit and integration tests, and CI workflow.

## Conclusion

AI Career & Resume Assistant is a compact, student-oriented project demonstrating how to combine server-side resume parsing with LLM-powered analysis and guidance. It is intended as a learning/demo project for final-year students to explore practical integrations between web apps and generative AI.

---

If you plan to run Gemini calls, ensure `GEMINI_API_KEY` is set in `.env` and `google-genai` is installed in the same Python environment used to run the Django app.
