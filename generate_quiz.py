import os
import json
import random
from google import genai
from dotenv import load_dotenv

from utils import send_email, get_markdown_files

load_dotenv(override=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_quiz():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = get_markdown_files(base_dir)
    use_note = random.choice([True, False])

    if use_note and md_files:
        chosen_file = random.choice(md_files)
        note_title = os.path.basename(chosen_file).replace('.md', '')
        with open(chosen_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        prompt_topic = f"the following study note ({note_title})"
        context_block = f"\nStudy Note Context:\n{md_content}\n"
    else:
        note_title = "General AI & ML (Surprise Topic!)"
        prompt_topic = "a broad, advanced topic within Social Media Analytics, Artificial Intelligence, or Machine Learning"
        context_block = ""

    # Call Gemini
    # Updated to use the new SDK call style
    pass

    prompt = f"""
    Act as a Senior AI/ML Interviewer. 
    Generate 3 scenario-based Multiple Choice Questions based on {prompt_topic}. 
    The questions must not be simple definitions; they must present a realistic engineering or data science scenario. 
    {context_block}
    
    Return EXACTLY a JSON object with this structure, and absolutely no other text or markdown formatting:
    {{
      "topic": "The general topic of the questions",
      "questions": [
        {{
          "id": 1,
          "scenario": "A detailed scenario describing an engineering problem...",
          "question": "What is the best approach to solve this?",
          "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
          "correct_answer_letter": "C",
          "correct_answer_text": "C) ...",
          "explanation": "Detailed explanation of why this is correct and others are wrong."
        }}
      ]
    }}
    """

    print("Calling Gemini API...")
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )

    quiz_data = json.loads(response.text)

    # Save the answers to latest_answers.json (for the answer email script)
    state_file = os.path.join(base_dir, ".github", "latest_answers.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, indent=2)

    # Also archive to Quiz-History/ so no quiz is ever lost
    import datetime
    history_dir = os.path.join(base_dir, "Quiz-History")
    os.makedirs(history_dir, exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    history_file = os.path.join(history_dir, f"quiz-{date_str}.json")
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, indent=2)

    print(f"Saved answers to {state_file} and archived to {history_file}")

    # Build the HTML Email
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1f2937; background-color: #f9fafb; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; border: 1px solid #e5e7eb; }}
            h1 {{ color: #4f46e5; font-size: 24px; margin-bottom: 5px; }}
            p.subtitle {{ color: #6b7280; font-size: 14px; margin-bottom: 30px; border-bottom: 1px solid #e5e7eb; padding-bottom: 20px; }}
            .question-card {{ background: #f3f4f6; padding: 20px; border-radius: 6px; margin-bottom: 20px; }}
            .scenario {{ font-style: italic; color: #374151; margin-bottom: 15px; }}
            .question {{ font-weight: bold; margin-bottom: 15px; font-size: 16px; }}
            .options {{ list-style-type: none; padding: 0; }}
            .options li {{ background: #ffffff; padding: 10px 15px; border: 1px solid #d1d5db; border-radius: 4px; margin-bottom: 8px; font-size: 14px; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #9ca3af; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Daily AI/ML Interview Prep</h1>
            <p class="subtitle">Topic: {quiz_data.get('topic', note_title)}</p>
            
            <p><strong>Heads up:</strong> The detailed answers and explanations will be sent to your inbox in exactly 30 minutes! Take your time to think through these scenarios.</p>
    """

    for q in quiz_data['questions']:
        options_html = "".join([f"<li>{opt}</li>" for opt in q['options']])
        html_content += f"""
            <div class="question-card">
                <div class="scenario">{q['scenario']}</div>
                <div class="question">{q['id']}. {q['question']}</div>
                <ul class="options">
                    {options_html}
                </ul>
            </div>
        """

    html_content += """
            <div class="footer">
                Automated by GitHub Actions | Gemini-2.5-Flash
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        f"Action Required: Daily AI Quiz ({quiz_data.get('topic', note_title)})",
        html_content,
    )


if __name__ == "__main__":
    generate_quiz()
