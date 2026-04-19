import os
import nltk
from collections import defaultdict

# Setup to avoid SSL certificate errors during NLTK downloads
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download required NLTK datasets (only downloads if not already present)
print("Checking/Downloading NLTK datasets...")
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# 1. Setup Data
doc_files = ['doc1.txt', 'doc2.txt', 'doc3.txt']
stop_words = set(stopwords.words('english'))

# 2. Initialize our Inverted Index
# This is our Dictionary mapping a term to its Postings List (a list of docIDs)
inverted_index = defaultdict(list)

print("\n--- Building Index ---")
# 3. Build the Index (The ETL Pipeline)
for doc_id, filename in enumerate(doc_files, start=1):
    print(f"Processing Document {doc_id}: {filename}")
    
    # Step 1: Read Document
    # We use the script's directory to find the files, no matter where the script is run from.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)
    
    with open(filepath, 'r', encoding='utf-8') as file:
        text = file.read()
        
    # Step 2: Tokenize
    tokens = word_tokenize(text)
    
    # Step 3: Normalize (Lowercase, remove punctuation, remove stopwords)
    normalized_tokens = []
    for token in tokens:
        token = token.lower() # Lowercase
        if token.isalpha() and token not in stop_words: # Remove punctuation and stop words
            normalized_tokens.append(token)
            
    print(f"   Tokens after normalization: {normalized_tokens}")
    
    # Step 4: Add to Index
    # We use set() to get unique terms in the current document.
    # We don't want to add the same docID twice to a posting list if a word appears twice!
    for term in set(normalized_tokens):
        # We append the docID. Since we process doc 1, then 2, then 3 sequentially, 
        # the postings lists are guaranteed to naturally be sorted in ascending order!
        inverted_index[term].append(doc_id)

print("\n--- Final Inverted Index ---")
# Print alphabetically sorted dictionary
for term, postings in sorted(inverted_index.items()):
    print(f"{term:<12} -> {postings}")

# --- Test a Boolean Query ---
print("\n--- Testing Boolean Query ---")

def intersect_postings(p1, p2):
    """Reusing our Two-Pointer Intersection Algorithm"""
    answer = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i] == p2[j]:
            answer.append(p1[i])
            i += 1; j += 1
        elif p1[i] < p2[j]:
            i += 1
        else:
            j += 1
    return answer

def union_postings(p1, p2):
    """Finds the union (OR) of two sorted postings lists."""
    answer = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i] == p2[j]:
            answer.append(p1[i])
            i += 1; j += 1
        elif p1[i] < p2[j]:
            answer.append(p1[i])
            i += 1
        else:
            answer.append(p2[j])
            j += 1
            
    # Add any remaining elements from either list
    while i < len(p1):
        answer.append(p1[i])
        i += 1
    while j < len(p2):
        answer.append(p2[j])
        j += 1
        
    return answer

query_word1 = 'brutus'
query_word2 = 'rome'

# Fetch postings from index, returning empty list if the word isn't in the index
p1 = inverted_index.get(query_word1, [])
p2 = inverted_index.get(query_word2, [])

print(f"Postings for '{query_word1}': {p1}")
print(f"Postings for '{query_word2}': {p2}")

# Test AND Query
result_and = intersect_postings(p1, p2)
print(f"\nResult for query '{query_word1} AND {query_word2}':")
print(f"-> Documents: {result_and}")

# Test OR Query
result_or = union_postings(p1, p2)
print(f"\nResult for query '{query_word1} OR {query_word2}':")
print(f"-> Documents: {result_or}")
