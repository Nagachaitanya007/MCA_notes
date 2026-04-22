import os
import random
import markdown
from google import genai
from dotenv import load_dotenv
import datetime
import re

from utils import send_email, get_markdown_files, save_note_to_db, generate_content_with_fallback

load_dotenv(override=True)

def send_daily_note():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = get_markdown_files(base_dir)

    prompt = "You are an Expert FAANG Engineering Manager. Write a highly detailed, deeply technical study note on an advanced concept within Machine Learning, Artificial Intelligence, or Generative AI. It must be interview-focused. Include detailed code snippets and real-world examples. Format the entire response in clean Markdown, starting with an H1 heading for the topic."
    
    print("Generating a new GenAI study note...")
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

    send_email(f"Daily Study Revision: {title}", email_html)


if __name__ == "__main__":
    send_daily_note()
