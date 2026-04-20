<div align="center">

# 🔥 NoteForge

**An AI-powered, self-growing knowledge base for FAANG interview preparation.**

Built with Next.js · Gemini AI · GitHub Actions · Render

[![Daily Notes](https://github.com/Nagachaitanya007/MCA_notes/actions/workflows/daily_email.yml/badge.svg)](https://github.com/Nagachaitanya007/MCA_notes/actions/workflows/daily_email.yml)
[![Daily Quiz](https://github.com/Nagachaitanya007/MCA_notes/actions/workflows/daily_quiz.yml/badge.svg)](https://github.com/Nagachaitanya007/MCA_notes/actions/workflows/daily_quiz.yml)

</div>

---

## What is NoteForge?

NoteForge is not a typical static notes website. It is a **fully automated content pipeline** that generates, publishes, and delivers interview-grade technical study material every single day — without any manual intervention.

Every morning, GitHub Actions triggers a set of Python scripts that use Google's Gemini AI to generate deep-dive study notes on topics like **Java & Spring Boot**, **System Design**, and **AI/ML**. These notes are committed back to the repository, automatically deployed to a live Next.js website via Render, and emailed directly to your inbox.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cron)                     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ daily_email   │  │ daily_quiz   │  │ note_java /       │  │
│  │ (10:00 AM)   │  │ (10:30 AM)   │  │ note_sys_design   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
│         │                 │                    │             │
│         ▼                 ▼                    ▼             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Python Automation Layer                  │    │
│  │  • Gemini AI content generation                      │    │
│  │  • Markdown → HTML email formatting                  │    │
│  │  • Gmail SMTP delivery                               │    │
│  │  • File saving with frontmatter metadata             │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                    git commit + push                         │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Render (Auto-Deploy) │
              │                       │
              │   Next.js Web App     │
              │   • Dark-themed UI    │
              │   • Search & filter   │
              │   • Markdown renderer │
              └───────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Content Generation** | Gemini 2.5 Flash generates unique, interview-focused study notes daily |
| 📧 **Automated Email Delivery** | Notes and quizzes delivered to your inbox on a schedule |
| 📝 **Interactive Quizzes** | Scenario-based MCQs with delayed answer delivery (30 min) |
| 🌐 **Live Web App** | Dark-themed Next.js site with search, filtering, and responsive design |
| 🔄 **CI/CD Pipeline** | GitHub Actions → git commit → Render auto-deploy |
| 📂 **Multi-Topic Support** | Java, System Design, AI/ML, and custom markdown notes |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| **AI Engine** | Google Gemini 2.5 Flash API |
| **Automation** | GitHub Actions (5 cron workflows) |
| **Backend Scripts** | Python 3.13 (google-generativeai, markdown, smtplib) |
| **Deployment** | Render (free tier, auto-deploy on push) |
| **Email** | Gmail SMTP with App Passwords |

## Daily Schedule (IST)

| Time | Workflow | What Happens |
|------|----------|-------------|
| 10:00 AM | `daily_email.yml` | Sends an AI-generated or existing note via email |
| 10:30 AM | `daily_quiz.yml` | Generates 3 MCQ questions and emails them |
| 11:00 AM | `daily_answers.yml` | Sends the quiz answers and explanations |
| 12:00 PM | `note_java.yml` | Generates a Java/Spring Boot deep-dive note |
| 1:00 PM | `note_system_design.yml` | Generates a System Design deep-dive note |

## Project Structure

```
MCA-notes/
├── .github/workflows/       # 5 GitHub Actions cron jobs
├── Generated-Notes/          # AI-generated markdown notes (auto-committed)
├── Social-Media-and-Text-Analysis/  # Manual study notes
├── notes-app/                # Next.js web application
│   ├── src/app/              # Pages and components
│   ├── src/lib/notes.ts      # Markdown file reader with frontmatter parsing
│   └── src/app/components/   # Reusable UI components
├── daily_mailer.py           # Sends daily AI/ML note
├── generate_study_note.py    # Generates topic-specific notes
├── generate_quiz.py          # Generates MCQ quizzes
├── send_answers.py           # Sends quiz answers
├── utils.py                  # Shared email & file utilities
└── render.yaml               # Render deployment config
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.13+
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)
- A [Gemini API Key](https://aistudio.google.com/app/apikey)

### Local Development

```bash
# Clone the repository
git clone https://github.com/Nagachaitanya007/MCA_notes.git
cd MCA_notes

# Set up Python environment
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the Next.js app
cd notes-app
npm install
npm run dev
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GMAIL_EMAIL` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not your regular password) |
| `GEMINI_API_KEY` | Google Gemini API key |

## License

This project is for educational and portfolio purposes.

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Nagachaitanya007">Naga Chaitanya</a></sub>
</div>
