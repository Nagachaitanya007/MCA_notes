"""
Shared utilities for the NoteForge automation pipeline.
Eliminates code duplication across daily_mailer, generate_study_note, generate_quiz, and send_answers.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from groq import Groq
import time
import json

load_dotenv(override=True)

# Clients initialized lazily
_gemini_client = None
_groq_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if key: _gemini_client = genai.Client(api_key=key)
    return _gemini_client

def get_groq_client():
    global _groq_client
    if _groq_client is None:
        key = os.environ.get("GROQ_API_KEY")
        if key: _groq_client = Groq(api_key=key)
    return _groq_client

def generate_content_with_fallback(prompt: str, is_json: bool = False) -> str:
    """
    Tries to generate content using a prioritized list of providers and models.
    Order: Gemini 2.0 Flash -> Gemini 2.0 Flash Lite -> Gemini Flash Latest -> Groq Llama 3.3
    """
    # 1. Try Gemini Models
    gemini = get_gemini_client()
    if gemini:
        gemini_models = ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-flash-latest']
        for model in gemini_models:
            for attempt in range(2):
                try:
                    print(f"Trying Gemini ({model}, attempt {attempt+1})...")
                    config = {'response_mime_type': 'application/json'} if is_json else None
                    response = gemini.models.generate_content(model=model, contents=prompt, config=config)
                    if response.text:
                        print(f"Success with Gemini ({model})!")
                        return response.text
                except Exception as e:
                    if "503" in str(e) or "429" in str(e):
                        print(f"Gemini {model} busy/limit reached. Waiting 5s...")
                        time.sleep(5)
                    else:
                        print(f"Gemini {model} error: {e}")
                        break # Try next model
    
    # 2. Fallback to Groq (The Shield)
    groq = get_groq_client()
    if groq:
        try:
            print("All Gemini options exhausted. Switching to Groq (Llama-3.3-70b)...")
            model = "llama-3.3-70b-versatile"
            response_format = {"type": "json_object"} if is_json else None
            
            chat_completion = groq.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                response_format=response_format
            )
            content = chat_completion.choices[0].message.content
            if content:
                print(f"Success with Groq ({model})!")
                return content
        except Exception as e:
            print(f"Groq failed as well: {e}")

    return ""


def get_supabase_client() -> Client:
    """Initializes and returns a Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Warning: Supabase credentials missing from .env")
        return None
    return create_client(url, key)


def save_note_to_db(title: str, content: str, folder: str, slug: str):
    """Saves a study note to the Supabase 'notes' table."""
    supabase = get_supabase_client()
    if not supabase: return
    
    try:
        data = {
            "title": title,
            "content": content,
            "folder": folder,
            "slug": slug
        }
        # Using upsert so if the same slug exists, it just updates it
        supabase.table("notes").upsert(data, on_conflict="slug").execute()
        print(f"Success! Note '{title}' saved to Supabase.")
    except Exception as e:
        print(f"Failed to save note to Supabase: {e}")


def save_quiz_to_db(topic: str, questions: list):
    """Saves a quiz to the Supabase 'quizzes' table."""
    supabase = get_supabase_client()
    if not supabase: return
    
    import datetime
    try:
        data = {
            "topic": topic,
            "questions": questions,
            "quiz_date": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        response = supabase.table("quizzes").insert(data).execute()
        print(f"Success! Quiz on '{topic}' saved to Supabase.")
    except Exception as e:
        print(f"CRITICAL DATABASE ERROR: Failed to save quiz to Supabase.")
        print(f"Error Details: {e}")


def get_email_config():
# ... (rest of the file)
    """Returns email configuration from environment variables."""
    return {
        "sender": os.environ.get("GMAIL_EMAIL"),
        "password": os.environ.get("GMAIL_APP_PASSWORD"),
        "receiver": os.environ.get("GMAIL_EMAIL"),  # Sending to self
    }


def send_email(subject: str, html_body: str):
    """
    Sends an HTML email via Gmail SMTP.
    Centralizes the SMTP connection logic that was previously duplicated across 4 scripts.
    """
    config = get_email_config()

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = config["receiver"]
    message.attach(MIMEText(html_body, "html"))

    try:
        print(f"Sending email: '{subject}'...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(config["sender"], config["password"])
        server.sendmail(config["sender"], config["receiver"], message.as_string())
        server.quit()
        print(f"Success! Sent: '{subject}'")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")
        raise


def get_markdown_files(directory: str) -> list[str]:
    """
    Recursively finds all .md files in the given directory,
    excluding app directories and special files.
    """
    md_files = []
    for root, dirs, files in os.walk(directory):
        # Ignore app directories and hidden folders
        if 'notes-app' in root or '.git' in root or 'node_modules' in root or 'scratch' in root:
            continue
        for file in files:
            if file.endswith(".md") and file not in [
                "implementation_plan.md",
                "task.md",
                "README.md",
                "walkthrough.md",
            ]:
                md_files.append(os.path.join(root, file))
    return md_files
