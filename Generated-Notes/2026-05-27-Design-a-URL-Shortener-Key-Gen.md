---
title: Scaling URL Shorteners: Distributed Range Allocation and Database Sharding
date: 2026-05-27T10:31:36.109368
---

# Scaling URL Shorteners: Distributed Range Allocation and Database Sharding

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine you are running a massive movie theater with 100 ticket booths. If every ticket booth had to call the main office every single time they sold a ticket to ask, *"Is ticket number #458,921 taken yet?"*, the entire theater line would grind to a halt. 

To solve this, the main office hands out **blocks of tickets** in advance. Ticket Booth A gets tickets `1 to 10,000`, Ticket Booth B gets `10,001 to 20,000`, and so on. Each booth can now sell tickets instantly from its own stack without talking to anyone else. 

In a URL Shortener, this is what a **Key Generation Service (KGS)** does. It hands out blocks of unique IDs (ranges) to different application servers. These servers convert those IDs into short strings (like `7bX9aP`) and match them with long URLs. 

But once you have billions of these links, they won't fit on a single database disk. So, we split the database into multiple smaller databases (called **Shards**). We then use the short link's ID to decide exactly which database shard will store it.

### Why should I care?
If you try to design a URL shortener by just auto-incrementing IDs in a single database (`SELECT MAX(id) FROM urls`), your system will crash under heavy load due to database lock contention. 

Using a distributed KGS with database sharding allows your system to:
1. Generate millions of unique short URLs per second with **zero database lock contention**.
2. Scale your storage infinitely by simply adding more cheap database servers (shards).

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Step-by-Step Flow

```
+--------------------------------------------------------------+
|                     1. ZooKeeper (Coordinator)               |
|            Tracks used ranges (e.g., Range: 1M - 2M)         |
+--------------------------------------------------------------+
                                |
             Allocates Range    |    Allocates Range
             [1,000 to 1,999]   |    [2,000 to 2,999]
                                v
+-------------------------------+    +-------------------------------+
|      KGS Node A (App Server)  |    |     KGS Node B (App Server)   |
|   Current Counter: 1005       |    |   Current Counter: 2042       |
+-------------------------------+    +-------------------------------+
                                |
                     Generates Base62 ID: 1005 -> "gH"
                                |
                                v
+--------------------------------------------------------------+
|                      2. Hash Ring Router                     |
|                Determines Shard: Hash("gH") % 3              |
+--------------------------------------------------------------+
                                |
                 +--------------+--------------+
                 |                             |
                 v                             v
+-------------------------------+    +-------------------------------+
|       Database Shard 1        |    |       Database Shard 2        |
|  Stores: {"gH": "google.com"} |    |             ...               |
+-------------------------------+    +-------------------------------+
```

1. **Range Allocation:** A coordination service (like Apache ZooKeeper) maintains a global counter. When a KGS application node boots up, it asks ZooKeeper for a range of IDs (e.g., `1,000,000 to 1,999,999`).
2. **Local Token Generation:** The KGS node increments its local memory counter for every new short URL request. It requires no network calls or database locks to get a new ID.
3. **Base62 Encoding:** The local base-10 ID (e.g., `20092183`) is encoded into a Base62 string (e.g., `1C7GZ`), which contains characters `[a-z, A-Z, 0-9]`. This makes the URL short and URL-safe.
4. **Database Routing (Sharding):** We hash the Base62 key to determine which physical database shard will store the record.

### Code Implementation (Base62 & Thread-Safe Local Allocator)

Here is how a single KGS worker node manages its assigned range and encodes IDs safely in memory.

```java
import java.util.concurrent.atomic.AtomicLong;

public class KGSWorkerNode {
    private static final String BASE62_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    private static final int BASE = BASE62_ALPHABET.length();

    private final long rangeEnd;
    private final AtomicLong currentCounter;

    public KGSWorkerNode(long rangeStart, long rangeEnd) {
        this.currentCounter = new AtomicLong(rangeStart);
        this.rangeEnd = rangeEnd;
    }

    // Thread-safe ID generation
    public synchronized String generateShortKey() {
        long nextId = currentCounter.getAndIncrement();
        if (nextId > rangeEnd) {
            throw new IllegalStateException("Range exhausted! Request a new block from coordinator.");
        }
        return encodeBase62(nextId);
    }

    // Helper method: Convert Base-10 Long to Base-62 String
    private String encodeBase62(long number) {
        StringBuilder sb = new StringBuilder();
        while (number > 0) {
            int remainder = (int) (number % BASE);
            sb.append(BASE62_ALPHABET.charAt(remainder));
            number /= BASE;
        }
        return sb.reverse().toString(); // Reverse to maintain correct significance order
    }

    public static void main(String[] args) {
        // Simulating a node allocated range [100000, 100005]
        KGSWorkerNode node = new KGSWorkerNode(100000, 100005);
        
        for (int i = 0; i < 6; i++) {
            System.out.println("Generated Short Key: " + node.generateShortKey());
        }
    }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Mechanics

#### 1. Range Allocation via Consensus (ZooKeeper)
To prevent two servers from using the same range, we use a strongly consistent distributed coordinator like Apache ZooKeeper.
- ZooKeeper stores a persistent node tracking the current global offset (e.g., `/global_counter = 12,000,000`).
- When KGS Node A needs a range, it updates this value to `13,000,000` via a compare-and-swap (CAS) operation and claims the range `[12,000,000 - 12,999,999]`.
- Even if ZooKeeper goes down, the active KGS nodes can continue serving writes until their current local ranges are completely exhausted.

#### 2. Sharding Strategies: Hash-Based vs. Consistent Hashing
Once we have our Base62 key (e.g., `3d9Gf`), we must write the mapping `3d9Gf -> https://example.com` to our database. To scale writes, we shard our databases.

*   **Modulo Sharding (`Hash(Key) % N`):** 
    Simple to implement. However, if you have 3 shards and need to scale to 4 because you are running out of space, the mathematical result of your modulo operation changes for almost all keys. This forces a massive, system-wide data migration.
*   **Consistent Hashing:**
    We map both database shards and keys to a 360-degree circular ring. A key is assigned to the next closest active database shard on the ring. When you add a new shard, you only have to move a small fraction of your keys ($1/N$), making scaling painless.

```
       [Shard 1] (0 degrees)
         /        \
        /          \  <-- Key "3d9Gf" hashes here (Goes to Shard 2)
  [Shard 3]      [Shard 2] (120 degrees)
 (240 degrees)     /
        \        /
         \      /
```

### Trade-offs & Systems Decisions

*   **Statelessness vs. Key Waste:** If a KGS node crashes or restarts, all unused IDs in its locally allocated memory block (e.g., 500,000 unused keys) are lost forever. 
    *   *The Trade-off:* This is an acceptable loss. With a 7-character Base62 key space, we have $62^7 \approx 3.5\text{ trillion}$ unique combinations. If we lose a few million keys due to server crashes, it won't impact our system capacity for decades.
*   **Consistent Hashing vs. Multi-master Replication:** Why not just use standard database replication?
    *   *The Trade-off:* Read replicas scale reads, but they don't scale write capacity. In a URL shortener, every new creation is a write. Sharding distributes write traffic across different physical disks, whereas standard replication duplicates every write to every node.

---

### Interviewer Probe Questions

#### Probe 1: "If we shard our database by `Hash(ShortKey)`, how do we redirect a user who visits our short URL? Does lookup require querying all shards?"
*   **Answer:** No. Because we use a deterministic hash function, the lookup process is identical to the write process. When a user requests `short.ly/3d9Gf`, the API gateway computes `Hash("3d9Gf") % Number_Of_Shards`. This instantly points directly to the exact shard holding that record, enabling $O(1)$ single-hop lookups.

#### Probe 2: "What happens if a single short URL goes viral (e.g., a breaking news tweet) and causes a hot partition on one database shard?"
*   **Answer:** While sharding distributes write traffic evenly, read traffic can become highly unbalanced due to viral links. We solve this by placing an in-memory caching layer (like Redis or Memcached) in front of the database shards. 
    - Popular keys are served entirely from cache memory.
    - We can use a consistent hashing ring for the cache cluster as well, and dynamically replicate extremely hot keys across multiple cache nodes to prevent any single cache server from melting.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Never use distributed locks or central DB increments for keys:** Use ZooKeeper to lease ranges of numeric IDs to isolated memory buffers on KGS nodes.
2. **Base62 is the industry standard:** Converting incremental integer keys (Base-10) to Base-62 (`[a-zA-Z0-9]`) shrinks string size while keeping keys highly readable and URL-compatible.
3. **Shard by Key Hash:** Use consistent hashing on the short key to balance database writes evenly across nodes and allow seamless scale-out.

### 1 Golden Rule
> **"For extreme write performance, trade absolute numeric continuity for isolation: let nodes own range blocks so they can generate IDs in memory without talking to anyone."**