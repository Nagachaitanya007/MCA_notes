# Gemini API Quiz Implementation Plan

I absolutely love this idea. Sending the answers 30 minutes later completely eliminates the temptation to peek, and having Gemini act as a broad AI/ML interviewer makes the system much more robust!

## The Architecture: State Passing
Because we are splitting this into two emails 30 minutes apart, we have a fun architectural challenge: **How does the 11:00 AM script know what questions the 10:30 AM script generated?** 

Since we can't ask Gemini "What did you say 30 minutes ago?" (it doesn't remember), we will use your GitHub repository as a database!
1. At 10:30 AM, our first script runs. It hits Gemini, generates the Quiz AND the detailed Answers. It sends the Quiz email immediately.
2. It then saves the Answers to a temporary file (`scratch/latest_answers.json`) and **automatically commits and pushes it to your GitHub repository**.
3. At 11:00 AM, our *second* script runs. It reads `scratch/latest_answers.json`, sends the detailed Answer email, and goes back to sleep.

This is highly professional and uses barely any of your free GitHub Actions quota (around 5 minutes a month!).

## Proposed Changes
1. **[NEW]** `generate_quiz.py`: 
   - Hits Gemini with a prompt to act as an AI/ML Interviewer covering Social Media Analytics, AI, and ML (drawing inspiration from your notes, but expanding beyond them).
   - Sends Email #1 (The Quiz).
   - Saves the detailed answers to `scratch/latest_answers.json`.
2. **[NEW]** `send_answers.py`:
   - Reads `scratch/latest_answers.json` and sends Email #2.
3. **[MODIFY]** `.github/workflows/daily_email.yml`:
   - We will create two separate "cron" triggers inside the GitHub action: one for 10:30 AM (05:00 UTC) and one for 11:00 AM (05:30 UTC), with logic to run the correct script based on the time.
4. **[MODIFY]** `requirements.txt`:
   - Add `google-generativeai`.

## Open Questions
> [!IMPORTANT]
> Because the script will automatically commit the `latest_answers.json` file back to your GitHub repository, you will see automated commits in your Git history. Are you okay with the script making commits to your repository?
