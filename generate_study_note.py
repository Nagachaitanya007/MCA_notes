import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

SENDER_EMAIL = os.environ.get("GMAIL_EMAIL")
SENDER_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("GMAIL_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def generate_and_send_note():
    if len(sys.argv) < 2:
        print("Usage: python generate_study_note.py \"<Topic String>\"")
        sys.exit(1)
        
    topic = sys.argv[1]
    
    print(f"Generating study note for topic: {topic}")
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        You are an Expert FAANG Engineering Manager and Technical Writer. 
        Write a highly detailed, deeply technical study note on an advanced concept within this topic: "{topic}". 
        It must be interview-focused and designed for a Senior Engineer. 
        Include detailed code snippets and real-world system architecture examples where applicable. 
        Format the entire response in clean Markdown, starting with an H1 heading for the specific concept you chose.
        """
        response = model.generate_content(prompt)
        md_content = response.text
    except Exception as e:
        print(f"Gemini generation failed: {e}")
        sys.exit(1)

    # Convert Markdown to HTML with syntax highlighting and tables support
    html_content = markdown.markdown(md_content, extensions=['fenced_code', 'codehilite', 'tables'])
    
    email_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1f2937; background-color: #f9fafb; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #ffffff; padding: 40px; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-top: 0; }}
            h2 {{ color: #374151; margin-top: 30px; }}
            h3 {{ color: #4b5563; }}
            pre {{ background-color: #1f2937; color: #f8fafc; padding: 15px; border-radius: 6px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; font-size: 14px; }}
            code {{ font-family: 'Courier New', Courier, monospace; background-color: #f1f5f9; padding: 2px 4px; border-radius: 4px; color: #ef4444; }}
            pre code {{ background-color: transparent; color: inherit; padding: 0; }}
            blockquote {{ border-left: 4px solid #3b82f6; background-color: #eff6ff; padding: 10px 20px; margin: 20px 0; font-style: italic; color: #1e3a8a; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
            th {{ background-color: #f9fafb; font-weight: 600; color: #374151; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {html_content}
            <div class="footer">
                Automated FAANG Interview Prep | Topic Focus: {topic}
            </div>
        </div>
    </body>
    </html>
    """

    # Setup the MIME
    message = MIMEMultipart("alternative")
    message["Subject"] = f"FAANG Deep Dive: {topic}"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    message.attach(MIMEText(email_html, "html"))

    try:
        print("Sending Email...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        server.quit()
        print(f"Success! Sent deep dive note for {topic}")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")

if __name__ == "__main__":
    generate_and_send_note()
