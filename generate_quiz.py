import os
import json
import random
import re
import sys

from dotenv import load_dotenv

from utils import send_email, get_markdown_files, save_quiz_to_db, generate_content_with_fallback

load_dotenv(override=True)

from smart_picker import pick_daily_topic

def generate_quiz():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get mode from command line (default to Java)
    mode = sys.argv[1] if len(sys.argv) > 1 else "Java"
    topic = pick_daily_topic(mode)
    
    print(f"Generating {mode} Quiz for topic: {topic}")

    if "MCA" in mode:
        # TCS iON Style MCA AI Exam Prompt
        prompt = f"""
        Act as a TCS iON Exam Designer for an MCA Artificial Intelligence course.
        Generate 3 high-quality, scenario-based Multiple Choice Questions based on: "{topic}".
        
        TCS iON Style Guidelines:
        - Every question must start with a "Real-world Industrial Problem Statement".
        - Focus on algorithm selection, data constraints, and performance trade-offs.
        - Options must be plausible (no obvious wrong answers).
        - Include questions on handling skewed data, high-dimensional spaces, or real-time constraints.
        """
    else:
        # Java Interview / Bug Hunting Prompt
        prompt = f"""
        Act as a Senior FAANG Interviewer.
        Generate 3 scenario-based Multiple Choice Questions based on: "{topic}".
        
        Interview Guidelines:
        - At least 1 question must be a "Bug Hunter" scenario (Provide a small Java/Spring snippet with a subtle flaw).
        - Use Markdown backticks (e.g. `List<String>`) for ALL code snippets and class names.
        - Focus on JVM Internals, Spring Proxies, Transaction Management, and Concurrency.
        - Scenario should be: "You are debugging a production issue where..."
        """

    prompt += f"""
    Return EXACTLY a JSON object with this structure, and absolutely no other text or markdown formatting:
    {{
      "topic": "{topic}",
      "mode": "{mode}",
      "questions": [
        {{
          "id": 1,
          "scenario": "Detailed problem statement or code snippet...",
          "question": "What is the primary cause of this issue?",
          "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
          "correct_answer_letter": "A",
          "correct_answer_text": "A) ...",
          "explanation": "Deep dive into why this is correct and the underlying mechanics (e.g., GC behavior, Proxy logic, or Algorithm math)."
        }}
      ]
    }}
    """

    print("Calling AI for quiz generation...")
    quiz_json = generate_content_with_fallback(prompt, is_json=True)
    
    if not quiz_json:
        print("CRITICAL: All AI providers failed.")
        sys.exit(1)

    try:
        # Clean up any potential markdown formatting from the response
        clean_json = re.sub(r'```json\s*|\s*```', '', quiz_json).strip()
        quiz_data = json.loads(clean_json)
    except Exception as e:
        print(f"Failed to parse quiz JSON: {e}")
        print("Raw response:", quiz_json)
        sys.exit(1)

    # Save the answers to latest_answers_{mode}.json (for the answer email script)
    state_file = os.path.join(base_dir, ".github", f"latest_answers_{mode}.json")
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

    # --- SAVE TO DATABASE ---
    save_quiz_to_db(
        topic=quiz_data.get("topic", "General"),
        questions=quiz_data.get("questions", [])
    )

    print(f"Saved answers to {state_file} and archived to {history_file}")

    # Build the HTML Email
    html_content_start = f"""
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
                max-width: 600px; 
                margin: 20px auto; 
                background: #ffffff; 
                padding: 30px 20px; 
                border-radius: 12px; 
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
            }}
            h1 {{ 
                color: #4f46e5; 
                font-size: 24px; 
                font-weight: 700; 
                margin-bottom: 5px;
            }}
            p.subtitle {{ 
                color: #718096; 
                font-size: 14px; 
                margin-bottom: 30px; 
                border-bottom: 1px solid #edf2f7; 
                padding-bottom: 20px; 
            }}
            .question-card {{ 
                background: #f8fafc; 
                padding: 25px; 
                border-radius: 12px; 
                margin-bottom: 25px; 
                border: 1px solid #e2e8f0;
            }}
            .scenario {{ 
                font-style: italic; 
                color: #4a5568; 
                margin-bottom: 20px; 
                font-size: 15px;
                line-height: 1.6;
                background: #ffffff;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #4f46e5;
            }}
            .question {{ 
                font-weight: 700; 
                margin-bottom: 20px; 
                font-size: 17px; 
                color: #2d3748;
            }}
            .options {{ 
                list-style-type: none; 
                padding: 0; 
            }}
            .options li {{ 
                background: #ffffff; 
                padding: 12px 18px; 
                border: 1px solid #e2e8f0; 
                border-radius: 8px; 
                margin-bottom: 10px; 
                font-size: 15px; 
                color: #4a5568;
                box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            }}
            .footer {{ 
                margin-top: 40px; 
                font-size: 12px; 
                color: #a0aec0; 
                text-align: center; 
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            @media (max-width: 600px) {{
                .container {{ margin: 0; border-radius: 0; padding: 25px 15px; }}
                .question-card {{ padding: 20px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{mode} Mastery Quiz</h1>
            <p class="subtitle">Topic: {quiz_data.get('topic', topic)}</p>
            
            <p style="background: #eef2ff; color: #3730a3; padding: 15px; border-radius: 8px; font-size: 14px; margin-bottom: 30px;">
                <strong>Hint:</strong> The detailed answers and explanations will arrive in exactly 30 minutes!
            </p>
    """

    import markdown
    for q in quiz_data['questions']:
        # Convert scenario markdown to HTML (safely handles < and > in code)
        html_scenario = markdown.markdown(q['scenario'], extensions=['fenced_code', 'tables'])
        
        # Still escape question and options for safety
        import html
        safe_question = html.escape(q['question'])
        options_html = "".join([f"<li>{html.escape(opt)}</li>" for opt in q['options']])
        
        html_content_start += f"""
            <div class="question-card">
                <div class="scenario">{html_scenario}</div>
                <div class="question">{q['id']}. {safe_question}</div>
                <ul class="options">
                    {options_html}
                </ul>
            </div>
        """

    html_content_start += """
            <div class="footer">
                NoteForge Technical Mastery | Automated Quiz Engine
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        f"Action Required: {mode} Mastery Quiz ({quiz_data.get('topic', topic)})",
        html_content_start,
    )


if __name__ == "__main__":
    generate_quiz()
