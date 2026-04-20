import os
import json
from dotenv import load_dotenv

from utils import send_email

load_dotenv(override=True)


def send_answers():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(base_dir, ".github", "latest_answers.json")

    if not os.path.exists(state_file):
        print(f"Error: Could not find {state_file}. Did the quiz run?")
        return

    with open(state_file, "r", encoding="utf-8") as f:
        quiz_data = json.load(f)

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1f2937; background-color: #f0fdf4; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; border: 1px solid #bbf7d0; }}
            h1 {{ color: #16a34a; font-size: 24px; margin-bottom: 5px; }}
            p.subtitle {{ color: #6b7280; font-size: 14px; margin-bottom: 30px; border-bottom: 1px solid #e5e7eb; padding-bottom: 20px; }}
            .answer-card {{ background: #f8fafc; border-left: 4px solid #16a34a; padding: 20px; margin-bottom: 20px; border-radius: 0 6px 6px 0; }}
            .question {{ font-weight: bold; margin-bottom: 10px; font-size: 16px; color: #374151; }}
            .correct-answer {{ color: #15803d; font-weight: bold; margin-bottom: 15px; font-size: 15px; background: #dcfce7; display: inline-block; padding: 5px 10px; border-radius: 4px; }}
            .explanation {{ color: #4b5563; font-size: 15px; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #9ca3af; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Answer Key &amp; Explanations</h1>
            <p class="subtitle">Topic: {quiz_data.get('topic', 'General AI/ML')}</p>
            
            <p>Here are the answers to your daily quiz. Let's see how you did!</p>
    """

    for q in quiz_data['questions']:
        html_content += f"""
            <div class="answer-card">
                <div class="question">{q['id']}. {q['question']}</div>
                <div class="correct-answer">Correct Answer: {q['correct_answer_text']}</div>
                <div class="explanation"><strong>Explanation:</strong> {q['explanation']}</div>
            </div>
        """

    html_content += """
            <div class="footer">
                Automated by GitHub Actions | Keep up the great studying!
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        f"Answers: Daily AI Quiz ({quiz_data.get('topic', 'General AI/ML')})",
        html_content,
    )


if __name__ == "__main__":
    send_answers()
