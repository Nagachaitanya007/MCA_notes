"""
Shared utilities for the NoteForge automation pipeline.
Eliminates code duplication across daily_mailer, generate_study_note, generate_quiz, and send_answers.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(override=True)


def get_email_config():
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
