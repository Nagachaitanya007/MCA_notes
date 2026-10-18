---
title: Pre-Minted Key Pools and Consistent Hash Sharding for High-Throughput URL Shorteners
date: 2026-10-18T10:34:23.318875
---

# Pre-Minted Key Pools and Consistent Hash Sharding for High-Throughput URL Shorteners

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
A URL shortener converts a long, unwieldy web address (like a 150-character tracking link) into a compact alias (like `https://sho.rt/x8K9q`). 

Under the hood, doing this for hundreds of millions of users introduces two classic distributed systems bottlenecks:
1. **Generating unique keys instantly** without running into collisions or database race conditions.
2. **Storing billions of mappings** across multiple database servers (sharding) without creating hot spots or bottlenecks.

#### The Real-World Analogy: The Coat Check Room
Imagine a coat check at a massive concert venue with 50,000 guests:
- **The Bad Way:** Every time someone hands you a coat, you sit down, grab a blank tag, try to think of a unique number, check a master ledger to see if anyone else has that number, and write it down. A massive line forms instantly.
- **The KGS Way (Pre-Minting):** Before the doors even open, an assistant prints 100,000 unique brass tags (`#1` through `#100,000`), shuffles them to prevent sequential guessing, and dumps them into buckets. When a guest arrives, the attendant grabs the next tag off the pile, pairs it with the coat, and hands it over. Zero hesitation. Zero collision checks.
- **The Sharding Way:** Instead of dumping all 50,000 coats onto one giant, collapsing rack, the venue has 16 numbered cloakrooms. The ticket number itself tells the staff exactly which cloakroom holds the coat.

#### Why should I care today?
Computing cryptographic hashes (like MD5 or SHA-256) at request time requires collision detection loops (`SELECT ... WHERE key = ?`). Under high concurrency, these loops lock rows, trigger retries, and spike latency. Decoupling key creation from link creation makes your write path blisteringly fast and eliminates transactional deadlocks.

---

### 2. 🛠️ How it Works (Step-by-Step)

```
[ Long URL ] ---> [ API Server ]
                        |
       1. Pulls Key     | 2. Hashes Key to pick Shard
      from Local Cache  v
    [ KGS Buffer ]   [ Consistent Hash Ring ]
                            |
                   +--------+--------+
                   |                 |
                   v                 v
            [ Shard 01 ]      [ Shard 02 ] ... [ Shard N ]
            (Stores: key -> original_url)
```

#### The Process:
1. **Offline Generation (Key Generation Service - KGS):** A standalone worker generates unique 7-character Base62 strings (`[a-zA-Z0-9]`) ahead of time. It stores them in a `keys` database with two states: `UNUSED` and `USED`.
2. **In-Memory Buffering:** API servers do not query the KGS database on every request. Instead, they lease batches of keys (e.g., 5,000 at a time) into local memory.
3. **Key Assignment:** When a user submits a long URL, the API server grabs a pre-allocated key from its memory queue.
4. **Consistent Hash Routing:** The system hashes the generated `short_key` using an algorithm like MurmurHash3 and maps it onto a Consistent Hash Ring to determine the target database shard.
5. **Persistence:** The API server writes the pair `(short_key, original_url, created_at)` directly to that designated shard.

#### Implementation: Key Vender & Shard Router

```python
import hashlib
import bisect
from collections import deque
from typing import List

class ShardRouter:
    """Consistent Hash Ring to map keys to database shards."""
    def __init__(self, shards: List[str], replicas: int = 100):
        self.replicas = replicas
        self.ring = []
        self.shard_map = {}

        for shard in shards:
            for i in range(replicas):
                # Distribute virtual nodes across the 32-bit integer space
                v_node_key = f"{shard}-vnode-{i}"
                v_hash = int(hashlib.md5(v_node_key.encode()).hexdigest(), 16)
                self.ring.append(v_hash)
                self.shard_map[v_hash] = shard

        self.ring.sort()

    def get_shard(self, short_key: str) -> str:
        if not self.ring:
            raise ValueError("No shards available.")
        
        # Hash the short key to locate its position on the ring
        key_hash = int(hashlib.md5(short_key.encode()).hexdigest(), 16)
        
        # Binary search for the first virtual node >= key_hash (wrapping if needed)
        idx = bisect.bisect_right(self.ring, key_hash)
        if idx == len(self.ring):
            idx = 0
            
        return self.shard_map[self.ring[idx]]


class KeyDispenser:
    """Simulates an API worker dispensing pre-minted keys from local buffer."""
    def __init__(self, pre_fetched_keys: List[str]):
        self.buffer = deque(pre_fetched_keys)

    def dispense_key(self) -> str:
        if not self.buffer:
            raise RuntimeError("Key buffer exhausted! Refill from KGS.")
        return self.buffer.popleft()


# --- Execution Example ---
if __name__ == "__main__":
    db_shards = ["db-shard-us-east", "db-shard-us-west", "db-shard-eu-central"]
    router = ShardRouter(shards=db_shards, replicas=150)
    
    # API node receives pre-allocated batch from KGS
    dispenser = KeyDispenser(["7bX9qA", "9mK2zL", "1vP4wE"])
    
    # Process a request
    long_url = "https://newsletter.pragmaticengineer.com/p/software-architecture"
    assigned_key = dispenser.dispense_key()
    target_shard = router.get_shard(assigned_key)

    print(f"Assigned Key : {assigned_key}")
    print(f"Target Shard : {target_shard}")
    print(f"Action       : INSERT INTO {target_shard}.urls VALUES ('{assigned_key}', '{long_url}')")
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### 1. Mathematical Mechanics: Base62 & Space Sizing
We use Base62 ($[A-Z, a-z, 0-9]$).
- A 6-character key yields: $62^6 \approx 56.8 \text{ billion combinations}$.
- A 7-character key yields: $62^7 \approx 3.52 \text{ trillion combinations}$.

At 1,000 writes/second, $3.52$ trillion keys will last **~111 years**. 

#### 2. Sharding Strategy: Partitioning by `short_key` vs. `user_id`
*   **Partitioning by `user_id`:** Groups a user's URLs together on one shard.
    *   *Failure Mode:* If a user goes viral or runs automated marketing, their shard becomes a severe hot spot. Read requests for redirects (`GET /x8K9q`) do not contain a `user_id`, forcing an expensive scatter-gather query across **all** shards.
*   **Partitioning by `hash(short_key)`:** Provides uniform distribution across the cluster.
    *   *Advantage:* Every lookup is an $O(1)$ deterministic point-query routed straight to the correct shard. Range scans are never needed for redirects.

#### 3. Trade-offs: Pre-Generating vs. Dynamic Hashing
| Metric | Dynamic Hashing (MD5/Murmur + Salt) | Pre-Minted Key Generation (KGS) |
| :--- | :--- | :--- |
| **Write Latency** | Variable (Collision retry loops under load) | Constant ($O(1)$ read from memory queue) |
| **Operational Overhead** | Low (No background services needed) | Medium/High (Requires token-broker infra) |
| **Crash Failure Mode** | No wasted keys | Lost keys if a node dies with local buffer |
| **DB Locking** | High contention on uniqueness constraints | Zero uniqueness checks required on write |

---

#### Interviewer Probes: How to Win the Follow-Up

##### Probe 1: *"If an API node crashes with 10,000 keys buffered in its memory, what happens to those keys?"*
> **Candidate Answer:** "We intentionally abandon and burn them. Because $62^7$ provides over 3.5 trillion keys, losing 10,000 keys is a negligible 0.00000028% loss of key space. Attempting to return unacknowledged keys back to the KGS introduces complex distributed tracking, two-phase commits, and risk of duplicate key assignment across nodes. Sacrificing leaked keys preserves strong consistency and zero-collision guarantees without distributed locks."

##### Probe 2: *"How do you handle duplicate URLs? If two users submit `https://google.com`, do they get the same short key?"*
> **Candidate Answer:** "In a high-scale production system, we deliberately allow duplicate short keys for the same long URL. Enforcing a global 1:1 mapping requires checking a reverse index (`long_url -> short_key`) across our sharded database before issuing a key. This introduces cross-shard distributed locks and read-before-write latency bottlenecks. Allowing duplicates treats every short link as an isolated event, preserving independent writes and giving users separate analytics on their links."

##### Probe 3: *"When adding a new database shard to the cluster, how do you prevent millions of redirect requests from hitting the wrong shard?"*
> **Candidate Answer:** "We rely on Consistent Hashing with virtual nodes. When a new physical shard is introduced, it claims ownership of fractional slices across the hash ring. Only $K/N$ keys need to be migrated (where $K$ is the total keys and $N$ is the number of shards), rather than a full cluster rehash ($K \pmod N$). During migration, we maintain a dual-read routing rule: if a key is hashed to the new shard and not found, the router falls back to the previous replica node before returning a 404."

---

### 4. ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Decouple Generation from Ingestion:** Never compute and validate unique keys on the live write path. Let a background KGS mint them, and cache batches in web workers.
2. **Route by the Shorthand Key:** Always shard the database by `hash(short_key)`. Reads only supply the short code; sharding by anything else forces scatter-gather queries that destroy read performance.
3. **Burn Keys on Worker Crashes:** Keys are functionally infinite ($3.5 \text{ trillion}$ at 7 chars). Never add distributed consensus overhead just to recover a lost batch of buffered keys.

#### 1 Golden Rule to Remember
> *"At massive scale, prefer burning cheap keys over coordinating expensive distributed locks."*