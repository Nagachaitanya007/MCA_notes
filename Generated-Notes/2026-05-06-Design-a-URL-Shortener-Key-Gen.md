---
title: Designing a Scalable Key Generation Service (KGS) & Database Sharding
date: 2026-05-06T10:31:32.427013
---

# Designing a Scalable Key Generation Service (KGS) & Database Sharding

1. 💡 **The "Big Picture" (Plain English):**
   - **What is it?** Imagine you are running a massive global raffle. You need to hand out billions of unique ticket numbers. If everyone just shouts out a number they think is unique, two people will eventually pick the same one (a **collision**). If everyone has to wait in one single line to get a number from one guy with a notebook, the line will stretch around the world (a **bottleneck**).
   - **The Real-World Analogy:** Think of a **Cinema Chain**. Instead of every local theater calling "Headquarters" every time they sell a seat, Headquarters sends each theater a "block" of 1,000 ticket stubs in advance. The local theater hands them out instantly. When they run low, they ask for another block.
   - **Why care?** In a URL shortener like Bitly, you can't afford to check `SELECT * FROM links WHERE short_url = 'abc'` every time you generate a link. It's too slow. You need a way to guarantee uniqueness at scale without slowing down the user.

2. 🛠️ **How it Works (Step-by-Step):**
   - **Step 1: The Key Warehouse (KGS):** We have a dedicated microservice (KGS) that maintains a table of unique, random strings (e.g., 6-character codes like `5fXz2p`).
   - **Step 2: Pre-loading:** The KGS doesn't read from the DB for every request. It pulls a "buffer" of keys (say, 5,000 keys) into its local RAM.
   - **Step 3: Rapid Delivery:** When an App Server needs a short URL, it asks the KGS. The KGS hands over a key from RAM instantly.
   - **Step 4: Sharding:** Once the URL is shortened, we store it. Since one database can't hold billions of rows, we **Shard** (split) the data. We use the key to determine which database server the data belongs to (e.g., Keys starting with A-M go to DB 1, N-Z go to DB 2).

### ASCII Flow:
```text
[ Database of Keys ] <--- 1. "Give me 1000 keys"
        |
[ Key Generation Service (KGS) ] <--- 2. Keeps keys in RAM
        |
        +---- [ App Server 1 ] ----> (User gets 'bit.ly/3xZ')
        |
        +---- [ App Server 2 ] ----> (User gets 'bit.ly/9mQ')
```

### Simple "Key Buffer" Logic (Pseudocode):
```python
class KeyProvider:
    def __init__(self):
        self.buffer = []
        self.batch_size = 1000

    def get_key(self):
        if not self.buffer:
            # Refill from DB when empty
            self.buffer = db.fetch_unused_keys(limit=self.batch_size)
            db.mark_as_used(self.buffer) # Atomic update
        
        return self.buffer.pop()

# The App Server calls this and gets a response in microseconds.
```

3. 🧠 **The "Deep Dive" (For the Interview):**

- **Concurrency & Locking:** To prevent two KGS instances from grabbing the same block of keys, we use a `SELECT FOR UPDATE` (Pessimistic Locking) or a `version_number` (Optimistic Locking) in the Key DB. This ensures "Exactly Once" delivery of a key block to the KGS.
- **The "Lost Keys" Trade-off:** If the KGS server crashes, all keys currently in its RAM buffer are **lost**. 
    - *Is this a problem?* For a URL shortener, no. We have billions of combinations (62^6). Losing 5,000 keys is a tiny price to pay for massive performance gains.
- **Sharding Strategies:**
    - **Range Based:** (e.g., `user_id` 1-1M). Easy to query, but leads to "Hot Shards" if most active users are in the same range.
    - **Hash Based:** We take `hash(key) % number_of_shards`. This distributes data evenly, but makes adding new database servers (resharding) very difficult.
- **Consistency vs. Availability:** KGS is usually designed for **Availability**. We'd rather risk losing a few keys than have the "Shorten URL" button stop working for users.

**Interviewer Probe 1: "How do you handle a 'Hot Key' in sharding?"**
*Answer:* If one specific short URL goes viral (e.g., a celebrity tweets a link), that specific shard will get crushed. We solve this by putting a **Cache (Redis)** in front of the shards. The database shouldn't even see the traffic for viral links.

**Interviewer Probe 2: "What if the KGS becomes a Single Point of Failure?"**
*Answer:* We run multiple KGS instances. We use a coordination service like **Zookeeper** to ensure each instance is assigned a unique "Key Range" so they never overlap.

4. ✅ **Summary Cheat Sheet:**
- **KGS** solves the bottleneck of generating unique IDs by pre-generating them and caching them in memory.
- **Sharding** solves the storage limit by splitting the mapping table across multiple physical database instances.
- **Key Loss** is an acceptable trade-off for the speed provided by in-memory buffering.

**The Golden Rule:** 
> "Never calculate uniqueness at the moment of creation; pre-allocate uniqueness to guarantee speed."