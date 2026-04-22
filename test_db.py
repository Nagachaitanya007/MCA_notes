import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"Checking Supabase URL: {url}")
print(f"Checking Key present: {'Yes' if key else 'No'}")

if not url or not key:
    print("Error: Credentials missing!")
    exit(1)

try:
    supabase = create_client(url, key)
    # Test insertion
    test_data = {"title": "Test Connection", "content": "Hello", "slug": "test-ping"}
    result = supabase.table("notes").upsert(test_data, on_conflict="slug").execute()
    print("SUCCESS: Database connection is working.")
    print(f"Response: {result}")
except Exception as e:
    print(f"FAILED: {str(e)}")
