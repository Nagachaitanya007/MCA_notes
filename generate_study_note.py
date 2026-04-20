import os
import sys
import json
import markdown
from google import genai
from dotenv import load_dotenv
import datetime
import re

from utils import send_email

load_dotenv(override=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_and_send_note():
    if len(sys.argv) < 2:
        print("Usage: python generate_study_note.py \"<Topic String>\"")
        sys.exit(1)

    topic = sys.argv[1]

    print(f"Generating study note for topic: {topic}")

    # --- TOPIC DEDUPLICATION ---
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tracker_file = os.path.join(base_dir, ".github", "covered_topics.json")
    
    # Load previously covered subtopics
    covered = {}
    if os.path.exists(tracker_file):
        with open(tracker_file, "r", encoding="utf-8") as f:
            covered = json.load(f)
    
    previously_covered = covered.get(topic, [])
    exclusion_list = ", ".join(previously_covered[-30:]) if previously_covered else "None yet"

    try:
        prompt = f"""
        You are an Expert FAANG Engineering Manager and Technical Writer. 
        Write a highly detailed, deeply technical study note on an advanced concept within this topic: "{topic}". 
        It must be interview-focused and designed for a Senior Engineer. 
        Include detailed code snippets and real-world system architecture examples where applicable. 
        Format the entire response in clean Markdown, starting with an H1 heading for the specific concept you chose.
        
        IMPORTANT: Do NOT cover any of these subtopics, as they have already been covered:
        [{exclusion_list}]
        Pick a completely different subtopic within "{topic}".
        """
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        md_content = response.text

        # Extract the subtopic from the H1 heading and save it
        h1_match = re.search(r'^#\s+(.*)', md_content, re.MULTILINE)
        new_subtopic = h1_match.group(1).strip() if h1_match else "Unknown"
        
        if topic not in covered:
            covered[topic] = []
        covered[topic].append(new_subtopic)
        
        os.makedirs(os.path.dirname(tracker_file), exist_ok=True)
        with open(tracker_file, "w", encoding="utf-8") as f:
            json.dump(covered, f, indent=2)
        print(f"Topic tracker updated: '{new_subtopic}' added under '{topic}'")

        # Save generated note to file
        generated_dir = os.path.join(base_dir, "Generated-Notes")
        os.makedirs(generated_dir, exist_ok=True)

        safe_topic = re.sub(r'[^a-zA-Z0-9]', '-', topic).strip('-')
        safe_topic = re.sub(r'-+', '-', safe_topic)[:30]
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-{safe_topic}.md"
        file_path = os.path.join(generated_dir, filename)

        frontmatter = f"---\ntitle: {new_subtopic}\ndate: {datetime.datetime.now().isoformat()}\n---\n\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + md_content)
        print(f"Saved generated note to: {file_path}")

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

    send_email(f"FAANG Deep Dive: {topic}", email_html)


if __name__ == "__main__":
    generate_and_send_note()
