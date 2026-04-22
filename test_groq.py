import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv(override=True)

api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("Error: GROQ_API_KEY not found in .env file!")
    exit(1)

try:
    print(f"Connecting to Groq...")
    client = Groq(api_key=api_key)
    
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "Explain the concept of 'Eventual Consistency' in 2 sentences.",
            }
        ],
        model="llama-3.3-70b-versatile",
    )
    
    print("\n--- GROQ RESPONSE ---")
    print(chat_completion.choices[0].message.content)
    print("----------------------")
    print("SUCCESS: Groq API is working perfectly and is LIGHTNING fast!")

except Exception as e:
    print(f"FAILED: {e}")
