---
title: Fault-Tolerant Token Ranges and Shard Routing in a High-Scale URL Shortener
date: 2026-07-18T10:31:59.205928
---

# Fault-Tolerant Token Ranges and Shard Routing in a High-Scale URL Shortener

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine you are building a system that turns a massive, ugly link like `https://verylongdomain.com/user/92842/profile?ref=promo&track=true` into a tiny, elegant link like `https://sho.rt/aB3x9`. 

To do this at a scale of **billions** of links, you need two things:
1. **A Unique Ticket Dispenser (The Key Generation Service or KGS):** To generate unique 6-to-8 character codes (like `aB3x9`) without any two users ever getting the same code.
2. **A Massive Filing Cabinet System (Database Sharding):** A single database will crash under the load of global traffic. Instead, we split the data across multiple smaller database servers (shards).

---

### The Real-World Analogy: The Mega Coat-Check
Imagine a colossal, city-sized concert venue with millions of attendees. 
* **Without our system:** Security tries to write down every guest's full description in a single giant logbook. The line stalls, the book fills up, and the receptionist gets overwhelmed (Single DB bottleneck).
* **With our system:** 
  * A dedicated machine prints numbered tickets in batches (KGS). Each ticketeer gets a roll of 1,000 unique tickets. They don't have to ask a central manager for permission for every single ticket; they just use their roll.
  * The coat closets are numbered 0 to 9. If your ticket ends in `3`, your coat goes to Closet 3 (Database Sharding). No single closet gets overloaded, and finding a coat takes seconds.

---

### Why should you care?
If you don't design this correctly:
* **Collisions happen:** Two different users get the same short URL, and one overrides the other.
* **Database Deadlocks:** Your database spends all its time checking `IF EXISTS` constraints rather than writing data.
* **System Outages:** A single celebrity post redirects millions of users to the same database partition, knocking your service offline.

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Architecture Workflow
```
[User Write Request] ---> [App Server]
                             |
                             +---> [1. Request Next Token Range] ---> [ZooKeeper (Coordinator)]
                             |
                             +---> [2. Dispense Base62 Token] 
                             |
                             +---> [3. Hash Token & Route] ---> [Database Shard 1, 2, or 3]
```

### The Step-by-Step Execution
1. **Range Allocation:** A coordination service (like Apache ZooKeeper) maintains a global counter. When an App Server starts up, it requests a range of numbers (e.g., IDs `1,000,000` to `1,999,999`).
2. **Local Token Dispensing:** The App Server keeps this range in memory. When a user requests a short URL, the server increments its local counter, converts the integer (e.g., `1000005`) to **Base62** (which looks like `aB3x9`), and assigns it. No database network calls are needed for this step.
3. **Shard Selection:** The App Server hashes the generated token to determine which database shard should store the mapping.
4. **Data Persistence:** The App Server writes the `(Token, LongURL)` record directly to the selected shard.

---

### Code Implementation: The Range-Based Token Dispenser & Shard Router

```python
import hashlib

class TokenDispenser:
    """
    Simulates the in-memory Key Generation Service (KGS) range allocation.
    In production, the range boundaries are fetched from ZooKeeper.
    """
    def __init__(self, range_start: int, range_end: int):
        self.current_id = range_start
        self.range_end = range_end
        # Base62 character set: [0-9][a-z][A-Z]
        self.BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _to_base62(self, num: int) -> str:
        """Converts an auto-incremented integer ID to a Base62 string."""
        if num == 0:
            return self.BASE62_ALPHABET[0]
        
        arr = []
        base = len(self.BASE62_ALPHABET)
        while num:
            num, rem = divmod(num, base)
            arr.append(self.BASE62_ALPHABET[rem])
        arr.reverse()
        return "".join(arr)

    def get_next_token(self) -> str:
        if self.current_id > self.range_end:
            raise IndexError("Token range exhausted! Request a new range from ZooKeeper.")
        
        token = self._to_base62(self.current_id)
        self.current_id += 1
        return token


class ShardRouter:
    """
    Determines which database shard should hold the mapping.
    Uses consistent hashing (simplified here to MurmurHash modulo).
    """
    def __init__(self, total_shards: int):
        self.total_shards = total_shards

    def get_shard_id(self, token: str) -> int:
        # We hash the token to ensure even distribution across all DB shards
        hash_value = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        return hash_value % self.total_shards


# --- Execution Walkthrough ---
if __name__ == "__main__":
    # 1. Initialize the Token Dispenser with an allocated range of 1 Million IDs
    dispenser = TokenDispenser(range_start=1000000, range_end=1999999)
    router = ShardRouter(total_shards=4)
    
    # 2. Simulate incoming requests
    long_urls = [
        "https://systemdesign.one/kgs-sharding",
        "https://github.com/trending",
        "https://news.ycombinator.com"
    ]
    
    for url in long_urls:
        token = dispenser.get_next_token()
        shard_id = router.get_shard_id(token)
        print(f"Long URL: {url:<40} -> Short Token: {token:<6} -> Save to DB Shard: {shard_id}")
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic: Range Allocation & Sharding Strategies
When scaling to **100,000+ writes per second**, standard SQL auto-increment columns become your primary bottleneck because they require global database locks. 

To bypass this bottleneck, we decouple token generation from storage:

#### 1. Distributed Range Allocation (The KGS Inner Workings)
* A consensus cluster (ZooKeeper) maintains a single persistent node containing the `CurrentGlobalCounter` (initialized to `0`).
* When an Application Server boots up, it updates the counter by adding `1,000,000` via a transactional Compare-And-Swap (CAS) operation.
* The App Server now "owns" the range `[CurrentGlobalCounter, CurrentGlobalCounter + 1,000,000]`.
* It increments this value in-memory using an `AtomicLong` (atomic CPU instructions, zero lock contention).

#### 2. Sharding Mechanics: Why Token-Based and Not User-ID Based?
If we shard our database by `UserID`, querying a short URL like `sho.rt/aB3x9` would force us to broadcast our read query to **every single database shard** because the token does not contain the `UserID` context. This is known as a **Scatter-Gather query**, and it is highly inefficient.

Instead, we shard by **the hash of the short token**. 
* **Write Path:** Calculate `Hash(Token) % Number_of_Shards` $\rightarrow$ Write directly to that shard.
* **Read Path (Redirects):** Calculate `Hash(Token) % Number_of_Shards` $\rightarrow$ Fetch directly from that shard (Single-node point-lookup, $O(1)$ complexity).

---

### Trade-Offs

| Option | Pros | Cons |
| :--- | :--- | :--- |
| **Range Allocation (ZooKeeper)** | Incredibly fast (RAM-speed token generation); guarantee of zero token collisions. | If an App Server crashes, the remaining keys in its allocated range are lost forever (abandoned range). |
| **Consistent Hashing** | Allows adding DB shards with minimal data migration. | Slightly more complex routing math; potential for uneven partition distribution if virtual nodes are not configured correctly. |

---

### Interviewer Probes (Tricky Questions & Advanced Answers)

#### Probe 1: "If an App Server crashes and we lose its allocated range of 1 million keys, don't we run out of short URLs quickly?"
* **Your Answer:** "No. A 7-character token in Base62 gives us $62^7 \approx 3.5\text{ Trillion}$ unique combinations. If we lose 1 million keys due to a server crash once a week, it would take us over **67,000 years** to run out of keys. The negligible key waste is a cheap price to pay for lock-free, ultra-high-throughput token generation."

#### Probe 2: "What happens if a popular tweet goes viral? Won't that specific DB Shard melt under the read volume (Hotspotting)?"
* **Your Answer:** "We do not let hot read traffic reach the database shards. We implement a multi-layered caching strategy:
  1. **CDN Layer (Edge):** Cache the most active redirects at the CDN level.
  2. **Distributed Cache (Redis):** Before querying the DB shards, check an in-memory cache cluster.
  3. Since redirects are immutable (a short URL mapping never changes), we can set a high Time-To-Live (TTL) on our cache. The DB shards are reserved almost exclusively for write paths and cache-miss cold reads."

#### Probe 3: "Why choose Base62 over Base64?"
* **Your Answer:** "Base64 includes characters like `+` and `/`. These characters have special meanings in URL parameters and HTTP paths, requiring URL-encoding (e.g., `/` becomes `%2F`). Base62 uses only alphanumeric characters (`a-z`, `A-Z`, `0-9`), making it entirely safe to use directly in URLs without encoding."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Never generate short keys on the fly using Database Locks.** Use an out-of-band Key Generation Service (KGS) using distributed range allocation (via ZooKeeper) to dispense ranges to App Servers in bulk.
2. **Shard by the Short Token Hash.** This guarantees that lookup queries are direct point-lookups on a single database shard, avoiding catastrophic scatter-gather reads.
3. **Handle Hotspots at the Caching Layer.** Do not scale your database partitions to handle read peaks; solve read hotspots using CDNs and a Redis write-through cache.

### 1 "Golden Rule"
> **Decouple generation from persistence.** The key generator should never need to ask the database if a key is unique; uniqueness must be guaranteed by the design of the range allocation itself.