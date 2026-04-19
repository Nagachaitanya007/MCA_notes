# Apache Solr: Query Examples

## 1. What is Apache Solr?
Apache Solr is a highly popular, open-source enterprise search platform built on top of **Apache Lucene**. 
Remember the **Inverted Index** and **Boolean Queries** we discussed earlier? Lucene is the underlying Java library that implements those exact concepts at scale, and Solr provides a wrapper around it so you can interact with the index easily using web requests (HTTP/REST APIs) and JSON.

## 2. Anatomy of a Solr Query
When you query Solr, you usually send an HTTP request to an endpoint. 
Example URL: `http://localhost:8983/solr/my_collection/select?q=...&fq=...`

Here are the most important parameters you need to know:
*   **`q` (Query):** The main search query. This is where you put your keywords or Boolean logic.
*   **`fq` (Filter Query):** Used to filter the result set *without* affecting the relevance score (e.g., filtering by date or category). It is highly cached and very fast.
*   **`fl` (Field List):** Specifies which fields to return in the results (similar to `SELECT author, title` in SQL).
*   **`sort`:** How to sort the results (e.g., `sort=price desc`). By default, it sorts by relevance score (`score desc`).
*   **`rows`:** How many results to return (default is usually 10).

---

## 3. Common Query Examples

### A. Basic Keyword Query
Searching for a single term across the default search field.
*   **Syntax:** `q=brutus`

### B. Boolean Queries (AND, OR, NOT)
Solr supports the exact same Boolean logic we discussed in our previous notes!
*   **AND:** `q=brutus AND caesar` (Documents must contain both)
*   **OR:** `q=brutus OR rome` (Documents containing either)
*   **NOT:** `q=rome NOT brutus` (Documents containing Rome, but excluding any that mention Brutus)
*   *Note: In Solr, you can also use `+` for MUST (AND) and `-` for MUST NOT (NOT). Example: `q=+rome -brutus`*

### C. Field-Specific Queries
In real datasets, documents have specific fields (like `title`, `author`, `body`). You use a colon `:` to search a specific field.
*   **Syntax:** `q=author:shakespeare`
*   **Combination:** `q=title:rome AND author:shakespeare`

### D. Phrase Queries
If you want to find exact word sequences, wrap them in double quotes.
*   **Syntax:** `q="ancient rome"`
*   *(This ensures "ancient" and "rome" appear right next to each other, unlike `q=ancient AND rome` which just checks if they both exist anywhere in the document).*

### E. Wildcards, Fuzzy, and Proximity Queries
*   **Wildcard:** `q=test*` (Matches "test", "testing", "tester")
*   **Fuzzy Search:** `q=roam~` (Finds words spelled similarly to "roam", like "rome" or "foam". Great for handling typos!)
*   **Proximity Search:** `q="brutus caesar"~10` (Finds "brutus" and "caesar" appearing within 10 words of each other).

---

## 4. Mental Map: Solr vs SQL
If you are familiar with SQL databases, here is a quick translation guide:

| SQL | Apache Solr |
| :--- | :--- |
| `SELECT title, author` | `fl=title,author` |
| `WHERE text LIKE '%brutus%'`| `q=text:brutus` |
| `WHERE category = 'history'` | `fq=category:history` |
| `ORDER BY date DESC` | `sort=date desc` |
| `LIMIT 10` | `rows=10` |
