import os
import json
from dotenv import load_dotenv

from utils import send_email

load_dotenv(override=True)


import sys

def send_answers():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mode = sys.argv[1] if len(sys.argv) > 1 else "Java"
    state_file = os.path.join(base_dir, ".github", f"latest_answers_{mode}.json")

    if not os.path.exists(state_file):
        print(f"Error: Could not find {state_file}. Did the quiz run?")
        return

    with open(state_file, "r", encoding="utf-8") as f:
        quiz_data = json.load(f)

    topic = quiz_data.get('topic', 'General')

    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap');
            
            body {{ 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
                line-height: 1.7; 
                color: #1a202c; 
                background-color: #f0fdf4; 
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
                border: 1px solid #bbf7d0;
            }}
            h1 {{ 
                color: #16a34a; 
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
            .answer-card {{ 
                background: #f8fafc; 
                padding: 25px; 
                border-radius: 12px; 
                margin-bottom: 25px; 
                border-left: 5px solid #16a34a;
            }}
            .question {{ 
                font-weight: 700; 
                margin-bottom: 15px; 
                font-size: 17px; 
                color: #2d3748;
            }}
            .correct-box {{ 
                background: #dcfce7; 
                color: #15803d; 
                padding: 10px 15px; 
                border-radius: 8px; 
                font-weight: 700;
                display: inline-block;
                margin-bottom: 20px;
                font-size: 14px;
            }}
            .explanation {{ 
                color: #4a5568; 
                font-size: 15px; 
                line-height: 1.6;
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
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{mode} Answer Key</h1>
            <p class="subtitle">Topic: {topic}</p>
            
            <p style="margin-bottom: 30px; color: #4a5568;">Here are the expert explanations for today's {mode} challenge.</p>
    """

    for q in quiz_data['questions']:
        html_content += f"""
            <div class="answer-card">
                <div class="question">{q['id']}. {q['question']}</div>
                <div class="correct-box">✅ Correct Answer: {q['correct_answer_text']}</div>
                <div class="explanation">
                    <strong>Deep Dive Explanation:</strong><br>
                    {q['explanation']}
                </div>
            </div>
        """

    html_content += f"""
            <div class="footer">
                NoteForge Technical Mastery | {mode} Quiz Series
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        f"Answer Key: {mode} Mastery Quiz ({topic})",
        html_content,
    )


if __name__ == "__main__":
    send_answers()
