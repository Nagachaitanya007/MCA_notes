# Text Processing Pipeline: Encoding, Tokenization, and Normalization

Before we can build an Inverted Index, raw text must be processed. This pipeline is the foundation of Natural Language Processing (NLP) and Information Retrieval (IR).

## 1. Text Encoding
At the hardware level, computers only understand `0`s and `1`s. 
*   **Concept:** Raw text is just a stream of bytes. To read it, we must know the **Encoding** (like UTF-8 or ASCII). 
*   **Why it matters:** If a document is encoded in `UTF-8` but your Python script reads it using `ASCII` or `Windows-1252`, special characters (like emojis, accents, or different alphabets) will turn into gibberish. Always use the appropriate decoder!

---

## 2. Tokenization: Tokens vs. Terms
Tokenization is the process of chopping up a sequence of characters into discrete units. But we must distinguish between two crucial concepts:

*   **Token:** A specific instance of a sequence of characters in a document. (The raw cut-out piece of text).
*   **Term:** A normalized string that actually becomes an entry in the dictionary of our Inverted Index.

**Example:**
*   Sentence: `"The dogs are running."`
*   **Tokens:** `["The", "dogs", "are", "running", "."]`
*   **Terms (after normalization):** `["dog", "run"]` *(Notice how "The", "are", and "." were dropped, and the words were reduced to their base forms).*

---

## 3. The Challenges of Tokenization
Tokenization sounds easy (just split by spaces!), but language is messy. Here are the major edge cases you must consider:

1.  **Apostrophes & Contractions:** 
    *   *Issue:* If you naively split by punctuation, `"Aren't"` becomes `"Aren"` and `"t"`, which loses the meaning of "not". 
    *   *Issue:* `"India's"` could become `"India"` and `"s"`. Do we keep the `"s"`?
2.  **Proper Names:**
    *   *Issue:* Splitting `"Derek O'Brain"` by punctuation creates `"Derek"`, `"O"`, `"Brain"`. The entity is destroyed.
3.  **Hyphenation:**
    *   *Issue:* Is `"state-of-the-art"` one token or four? If we split it, a search for `"state"` might incorrectly match this document.

---

## 4. The Golden Rule of Information Retrieval
> **The exact same processing pipeline used to index the documents MUST be applied to the user's search query.**

**Why? (The Plural/Singular Issue)**
Imagine a document says: `"The students are studying."`
If your indexer converts plurals to singulars, the indexed term is **`student`**.
If a user searches for `"students"`, and you *don't* process their query, you will look up the term **`students`** in your dictionary. It won't be there! There will be **zero matches**. 

---

## 5. Lemmatization and Stemming
To solve the plural/singular issue, we use techniques to reduce words to their base forms:

*   **Stemming:** A crude, rule-based approach that chops off the ends of words. 
    *   *Example:* `"Studying"`, `"Studies"`, `"Student"` $\rightarrow$ `"Studi"`
    *   *Pros/Cons:* Very fast, but often creates non-real words.
*   **Lemmatization:** A smarter, dictionary-based approach that understands vocabulary and context to return the proper root word (the "lemma").
    *   *Example:* `"Better"` $\rightarrow$ `"Good"`. `"Am", "Are", "Is"` $\rightarrow$ `"Be"`.
    *   *Pros/Cons:* Highly accurate and produces real words, but computationally slower.

## 6. Stop Words
Stop words are extremely common words (`"the"`, `"is"`, `"at"`, `"which"`) that hold very little search value.
*   **Action:** We drop them entirely during the tokenization phase.
*   **Benefit:** This drastically reduces the size of our dictionary and postings lists, saving memory and speeding up queries.
