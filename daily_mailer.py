import os
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from a hidden .env file (override any existing system vars)
load_dotenv(override=True)

# --- CONFIGURATION ---
# The script will now pull these securely from your environment variables.
SENDER_EMAIL = os.environ.get("GMAIL_EMAIL")
SENDER_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("GMAIL_EMAIL") # Sending to yourself
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_markdown_files(directory):
    md_files = []
    for root, dirs, files in os.walk(directory):
        # Ignore app directories and hidden folders
        if 'notes-app' in root or '.git' in root or 'node_modules' in root or 'scratch' in root:
            continue
        for file in files:
            if file.endswith(".md") and file not in ["implementation_plan.md", "task.md", "README.md", "walkthrough.md"]:
                md_files.append(os.path.join(root, file))
    return md_files

def send_daily_note():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = get_markdown_files(base_dir)
    
    use_local_note = random.choice([True, False])
    
    if use_local_note and md_files:
        # Pick a random note
        chosen_file = random.choice(md_files)
        title = os.path.basename(chosen_file).replace('.md', '')
        with open(chosen_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
    else:
        # Generate a new AI/GenAI note via Gemini
        print("Generating a new GenAI study note...")
        import datetime
        import re
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = "You are an Expert FAANG Engineering Manager. Write a highly detailed, deeply technical study note on an advanced concept within Machine Learning, Artificial Intelligence, or Generative AI. It must be interview-focused. Include detailed code snippets and real-world examples. Format the entire response in clean Markdown, starting with an H1 heading for the topic."
            response = model.generate_content(prompt)
            md_content = response.text
            title = "AI/GenAI Deep Dive (Generated)"
            
            # --- NEW FILE SAVING LOGIC ---
            generated_dir = os.path.join(base_dir, "Generated-Notes")
            os.makedirs(generated_dir, exist_ok=True)
            
            match = re.search(r'^#\s+(.*)', md_content, re.MULTILINE)
            extracted_title = match.group(1) if match else "GenAI-Deep-Dive"
            safe_topic = re.sub(r'[^a-zA-Z0-9]', '-', extracted_title).strip('-')
            safe_topic = re.sub(r'-+', '-', safe_topic)[:30]
            
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            filename = f"{date_str}-{safe_topic}.md"
            file_path = os.path.join(generated_dir, filename)
            
            frontmatter = f"---\ntitle: {extracted_title}\ndate: {datetime.datetime.now().isoformat()}\n---\n\n"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(frontmatter + md_content)
            print(f"Saved generated note to: {file_path}")
            
        except Exception as e:
            print(f"Gemini generation failed: {e}. Falling back to local note.")
            if md_files:
                chosen_file = random.choice(md_files)
                title = os.path.basename(chosen_file).replace('.md', '')
                with open(chosen_file, 'r', encoding='utf-8') as f:
                    md_content = f.read()
            else:
                return

    # Convert Markdown to HTML
    html_content = markdown.markdown(md_content)
    
    # Wrap in a nice HTML template
    email_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            h1 {{ color: #4f46e5; }}
            h2 {{ color: #3730a3; }}
            code {{ background-color: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #888; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <p>Here is your daily study revision note!</p>
            <hr>
            {html_content}
            <div class="footer">
                Automated Daily Mailer | Sent from your local machine.
            </div>
        </div>
    </body>
    </html>
    """

    # Setup the MIME
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Daily Study Revision: {title}"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    message.attach(MIMEText(email_html, "html"))

    # Connect to Gmail Server and Send
    try:
        print("Connecting to SMTP server...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        server.quit()
        print(f"Success! Sent daily note: '{title}' to {RECEIVER_EMAIL}")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")
        print("\nNote: Have you updated the SENDER_EMAIL and SENDER_PASSWORD in the script?")

if __name__ == "__main__":
    send_daily_note()
