import os
import random
import markdown
from dotenv import load_dotenv
import datetime
import re

from utils import send_email, get_markdown_files, save_note_to_db, generate_content_with_fallback

load_dotenv(override=True)

import sys

def send_daily_note():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = get_markdown_files(base_dir)

    topic = sys.argv[1] if len(sys.argv) > 1 else "Advanced AI & Generative AI"

    prompt = f"""
    You are an Expert FAANG Interviewer and Senior Staff Engineer.
    Write a definitive, deeply technical interview study note on this topic: "{topic}".
    
    Structure:
    1. 🧱 The Core Concept (Basics Refresh)
    2. ⚙️ Under the Hood (Internal Mechanics & Architecture)
    3. ⚠️ The Interview Warzone (Scenario-based questions, Probing patterns, and the Perfect Response)
    
    Focus on real-world application and trade-offs. Format in clean Markdown.
    """
    
    print(f"Generating AI study note for topic: {topic}...")
    md_content = generate_content_with_fallback(prompt)
    
    if not md_content:
        print("CRITICAL: All AI providers failed. Falling back to local note.")
        if md_files:
            chosen_file = random.choice(md_files)
            title = os.path.basename(chosen_file).replace('.md', '')
            with open(chosen_file, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # Wrap local content to proceed normally
            extracted_title = title
        else:
            print("No local notes found to fall back on. Exiting.")
            return
    else:
        # We have fresh AI content!
        pass
    
    # Save generated note to file & database
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
    print(f"Saved note to: {file_path}")

    # --- SAVE TO DATABASE ---
    save_note_to_db(
        title=extracted_title,
        content=md_content,
        folder="Daily Note",
        slug=f"{date_str}-{safe_topic}"
    )
    
    title = extracted_title

    # Convert Markdown to HTML
    html_content = markdown.markdown(md_content)

    # Wrap in a nice HTML template
    email_html = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap');
            
            body {{ 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
                line-height: 1.7; 
                color: #1a202c; 
                background-color: #f7fafc; 
                margin: 0; 
                padding: 0;
            }}
            .container {{ 
                max-width: 650px; 
                margin: 20px auto; 
                background: #ffffff; 
                padding: 30px 20px; 
                border-radius: 12px; 
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
            }}
            h1 {{ 
                color: #2d3748; 
                font-size: 24px; 
                font-weight: 700; 
                letter-spacing: -0.02em;
                border-left: 4px solid #4f46e5;
                padding-left: 15px;
                margin-bottom: 25px;
            }}
            h2 {{ color: #4a5568; font-size: 20px; margin-top: 35px; }}
            
            /* Code Block Mastery */
            pre {{ 
                background-color: #1a202c; 
                color: #e2e8f0; 
                padding: 20px; 
                border-radius: 8px; 
                overflow-x: auto; 
                font-family: 'JetBrains Mono', 'Courier New', monospace; 
                font-size: 14px;
                line-height: 1.5;
                margin: 20px 0;
                border: 1px solid #2d3748;
            }}
            code {{ 
                font-family: 'JetBrains Mono', monospace; 
                background-color: #edf2f7; 
                padding: 3px 6px; 
                border-radius: 4px; 
                color: #e53e3e; 
                font-size: 0.9em;
            }}
            
            .footer {{ 
                margin-top: 50px; 
                font-size: 12px; 
                color: #a0aec0; 
                text-align: center; 
                border-top: 1px solid #edf2f7; 
                padding-top: 25px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            @media (max-width: 600px) {{
                .container {{ margin: 0; border-radius: 0; padding: 20px 15px; }}
                h1 {{ font-size: 22px; }}
                pre {{ font-size: 13px; padding: 15px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <p style="color: #4f46e5; font-weight: 600; margin-bottom: 10px;">Daily Revision Note</p>
            {html_content}
            <div class="footer">
                NoteForge Technical Mastery | Automated Daily Revision
            </div>
        </div>
    </body>
    </html>
    """

    send_email(f"Daily Study Revision: {title}", email_html)


if __name__ == "__main__":
    send_daily_note()
