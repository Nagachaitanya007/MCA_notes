import os
import sys
import json
import markdown

from dotenv import load_dotenv
import datetime
import re

from utils import send_email, save_note_to_db, generate_content_with_fallback

load_dotenv(override=True)

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

    prompt = f"""
    You are a world-class Technical Mentor and Interview Coach.
    Your goal is to explain "{topic}" so clearly that a junior dev understands it, but a senior dev respects the depth.
    
    Topic: "{topic}"
    
    Structure your note like this:

    # [Specific Subtopic Name Here]

    1. 💡 The "Big Picture" (Plain English):
       - What is this in simple terms?
       - Use a real-world analogy (e.g., a restaurant, a library, a bank).
       - Why should I care? What problem does it solve for me today?

    2. 🛠️ How it Works (Step-by-Step):
       - Break down the process into simple steps (1, 2, 3...).
       - Show a clean, well-commented code snippet.
       - Use a Mermaid diagram or ASCII art to show the flow.

    3. 🧠 The "Deep Dive" (For the Interview):
       - Now, explain the technical 'magic' (Internals, JVM, Database locking, etc.).
       - What are the trade-offs? (e.g. "It's faster, but uses more memory").
       - Explain 2-3 "Interviewer Probe" questions (how they ask this in a tricky way).

    4. ✅ Summary Cheat Sheet:
       - 3 Key Takeaways.
       - 1 "Golden Rule" to remember for this topic.

    IMPORTANT: 
    - Start with a single # H1 heading for the specific subtopic you chose.
    - Avoid unnecessary jargon in the first two sections.
    - Focus on "{topic}".
    - Do NOT cover these already-covered subtopics: [{exclusion_list}]
    """

    md_content = generate_content_with_fallback(prompt)
    
    if not md_content:
        print("CRITICAL: All AI providers failed.")
        sys.exit(1)

    # Extract the subtopic from the H1 heading and save it
    h1_match = re.search(r'^#\s+(.*)', md_content, re.MULTILINE)
    new_subtopic = h1_match.group(1).strip() if h1_match else "Unknown"
    
    if topic not in covered:
        covered[topic] = []
    covered[topic].append(new_subtopic)
    
    print(f"Topic tracker updated: '{new_subtopic.encode('ascii', 'ignore').decode()}' added under '{topic}'")
    
    os.makedirs(os.path.dirname(tracker_file), exist_ok=True)
    with open(tracker_file, "w", encoding="utf-8") as f:
        json.dump(covered, f, indent=2)
    print(f"Topic tracker saved.")

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

    # --- SAVE TO DATABASE ---
    save_note_to_db(
        title=new_subtopic,
        content=md_content,
        folder=topic,
        slug=f"{date_str}-{safe_topic}"
    )

    # Convert Markdown to HTML with syntax highlighting and tables support
    html_content = markdown.markdown(md_content, extensions=['fenced_code', 'codehilite', 'tables'])

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
            h3 {{ color: #718096; font-size: 18px; }}
            
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
            pre code {{ background-color: transparent; color: inherit; padding: 0; }}
            
            blockquote {{ 
                border-left: 4px solid #4f46e5; 
                background-color: #f0f4ff; 
                padding: 15px 25px; 
                margin: 25px 0; 
                font-style: italic; 
                color: #3730a3;
                border-radius: 0 8px 8px 0;
            }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                margin: 25px 0; 
                font-size: 14px;
            }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background-color: #f8fafc; font-weight: 600; color: #4a5568; }}
            
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
            {html_content}
            <div class="footer">
                NoteForge Technical Mastery | Topic: {topic}
            </div>
        </div>
    </body>
    </html>
    """

    send_email(f"FAANG Deep Dive: {topic}", email_html)


if __name__ == "__main__":
    generate_and_send_note()
