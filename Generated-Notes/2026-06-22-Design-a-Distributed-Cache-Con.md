---
title: Mastering Distributed Cache Design: Consistent Hashing & LRU Eviction Under the Hood
date: 2026-06-22T10:32:07.074287
---

# Mastering Distributed Cache Design: Consistent Hashing & LRU Eviction Under the Hood

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
A **Distributed Cache** is a system that stores frequently accessed data across a cluster of multiple machines. 

To build a great one, we must solve two fundamental problems:
1. **Routing (Consistent Hashing):** When a request comes in, how do we quickly decide *which* machine in our cluster should store or retrieve that specific piece of data, without causing a massive reorganization when servers are added or removed?
2. **Eviction (LRU Cache):** When an individual machine runs out of RAM, how does it gracefully throw away old data to make room for new data?

#### The Real-World Analogy
Imagine a massive, high-end library with millions of books, run by a team of librarians (Cache Nodes). 

* **The Problem:** If a visitor asks for a book, how do they know *which* librarian has it? If we simply assign books based on the total number of librarians (e.g., `Book ID % Number of Librarians`), everything breaks the moment a librarian goes on a lunch break or a new one is hired. Every single book in the library would have to change hands!
* **Consistent Hashing** is like placing all librarians in a circle. When a book comes in, you find its spot on the circle and walk clockwise to the nearest librarian. If a librarian leaves, only *their* books are handed to their neighbor. Everyone else keeps working undisturbed.
* **LRU (Least Recently Used) Eviction** is what each librarian does at their desk. Each librarian has a small desk that holds only 10 books. When the desk is full and a new book arrives, the librarian looks at their desk, finds the book that hasn't been opened for the longest time, and puts it back in the deep archives (the slow Database) to free up space.

#### Why should I care?
Without this pattern, modern applications like Netflix, Spotify, or Uber could not scale. If your database gets hit with millions of queries per second, it will crash. A distributed cache shields your database. 

By mastering **Consistent Hashing + LRU**, you prevent "Cache Stampedes," handle server crashes seamlessly, and keep your memory footprint lean.

---

### 2. 🛠️ How it Works (Step-by-Step)

#### The Process Flow
1. **The Request:** The client requests key `"user_42"`.
2. **The Ring Lookup (Consistent Hashing):**
   - The key `"user_42"` is hashed to a numeric value (e.g., `350,120`).
   - The system looks at the **Hash Ring** (a circular space of numbers from $0$ to $2^{32}-1$).
   - It finds the first server node whose hash value is greater than or equal to `350,120` (moving clockwise). Let's say it's **Server B**.
3. **The Node Request:** The request is routed directly to **Server B**.
4. **Local Eviction Check (LRU):**
   - **Server B** checks its local LRU cache.
   - **Cache Hit:** If `"user_42"` is found, it is moved to the "Most Recently Used" end of the list and returned.
   - **Cache Miss:** If not found, Server B fetches it from the database, saves it locally, and returns it. If Server B's memory is full, it evicts its least recently used key.

```
       [ Client Request: Get("user_42") ]
                       │
                       ▼
         [ Hash Key: SHA-256("user_42") ]
                       │
                       ▼
          [ Consistent Hash Ring Search ]
           0 ─────────────────────────► 2^32-1
           [Node A] ──► (user_42 Hash) ──► [Node B]
                       │
                       ├───► Route to [Node B]
                       ▼
             [ Node B's LRU Cache ]
             ┌────────────────────┐
             │ Hash Map (Lookup)  │ ──┐
             └────────────────────┘   │ (O(1) Access)
             ┌────────────────────┐   │
             │ Doubly Linked List │ ◄─┘
             │  [Head] ... [Tail] │ (Track Recency)
             └────────────────────┘
```

#### Code Implementation: A Complete Python Prototype
Here is a functional, elegant implementation gluing together a **Consistent Hash Ring** and a local **LRU Cache**.

```python
import hashlib
import bisect
from collections import OrderedDict

# ==========================================
# Component 1: Local LRU Cache (Per Node)
# ==========================================
class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        # OrderedDict in Python preserves insertion order, perfect for LRU
        self.cache = OrderedDict()

    def get(self, key: str) -> str:
        if key not in self.cache:
            return None
        # Move the accessed key to the end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: str) -> str:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            # Pop the first item (least recently used)
            evicted_key, _ = self.cache.popitem(last=False)
            return evicted_key
        return None

# ==========================================
# Component 2: Consistent Hashing Ring
# ==========================================
class ConsistentHashRing:
    def __init__(self, replicas=3):
        self.replicas = replicas  # Virtual nodes per physical node
        self.ring = []            # Sorted list of virtual node hashes
        self.vnode_map = {}       # Map: vnode_hash -> physical_node_name

    def _hash(self, key: str) -> int:
        # Use SHA-256 mapped to an integer space [0, 2^32 - 1]
        sha = hashlib.sha256(key.encode('utf-8')).hexdigest()
        return int(sha, 16) % (2**32)

    def add_node(self, node: str):
        """Adds a physical node to the ring via multiple virtual nodes."""
        for i in range(self.replicas):
            vnode_key = f"{node}-vnode-{i}"
            vnode_hash = self._hash(vnode_key)
            # Insert in sorted order
            bisect.insort(self.ring, vnode_hash)
            self.vnode_map[vnode_hash] = node

    def remove_node(self, node: str):
        """Removes a physical node's virtual tokens from the ring."""
        for i in range(self.replicas):
            vnode_key = f"{node}-vnode-{i}"
            vnode_hash = self._hash(vnode_key)
            self.ring.remove(vnode_hash)
            del self.vnode_map[vnode_hash]

    def get_node(self, key: str) -> str:
        """Finds the nearest node clockwise for a given key."""
        if not self.ring:
            return None
        key_hash = self._hash(key)
        # Binary search for the first virtual node with a hash >= key_hash
        idx = bisect.bisect_right(self.ring, key_hash)
        # If we fall off the end of the ring, wrap around to index 0
        if idx == len(self.ring):
            idx = 0
        return self.vnode_map[self.ring[idx]]

# ==========================================
# Component 3: The Distributed Cache Manager
# ==========================================
class DistributedCache:
    def __init__(self, node_names, node_capacity=2):
        self.ring = ConsistentHashRing(replicas=3)
        self.nodes = {}  # Map: node_name -> LRUCache instance
        
        for name in node_names:
            self.ring.add_node(name)
            self.nodes[name] = LRUCache(capacity=node_capacity)

    def put(self, key: str, value: str):
        target_node = self.ring.get_node(key)
        print(f"🔑 Key '{key}' routed to node: [{target_node}]")
        evicted = self.nodes[target_node].put(key, value)
        if evicted:
            print(f"   ⚠️  [Node {target_node}] Memory Full! Evicted: '{evicted}'")

    def get(self, key: str) -> str:
        target_node = self.ring.get_node(key)
        val = self.nodes[target_node].get(key)
        return val

# --- Demonstration Run ---
if __name__ == "__main__":
    # Initialize a cluster of 3 servers
    cluster = DistributedCache(node_names=["Server_A", "Server_B", "Server_C"], node_capacity=2)
    
    # Insert data
    cluster.put("user_1", "Alice")
    cluster.put("user_2", "Bob")
    cluster.put("user_3", "Charlie")
    cluster.put("user_4", "David") # This will trigger evictions due to small capacity
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### Architectural Magic: Virtual Nodes (Vnodes)
If we only place physical nodes (e.g., Server A, B, and C) on the hash ring, they will likely be distributed unevenly. This leads to **Hotspots** (one server owning 70% of the ring while others sit idle).

* **The Fix:** Virtual Nodes. We map each physical server to hundreds of virtual positions (e.g., `Server_A#1`, `Server_A#2`, `Server_A#3`). This interleaves the ownership ranges around the ring, guaranteeing an incredibly uniform load distribution (usually within $2-5\%$ variance).

```
   Without Virtual Nodes (Unbalanced):
   [───Server A───►║───────Server B───────►║─Server C─►] (Server B overloaded)

   With Virtual Nodes (Interleaved & Balanced):
   [──A#1──► B#1──► C#1──► A#2──► B#2──► C#2──►]
```

#### Why LRU Uses a HashMap + Doubly Linked List
A common interview trap is asking: *"Why not just use an Array or a singly linked list for the LRU Cache?"*
* **Array:** Checking if an item exists is $O(1)$ if sorted, but inserting/updating requires shifting elements which is $O(N)$.
* **Singly Linked List:** Finding the element to update takes $O(N)$ because you have to traverse from the head.
* **The Hybrid Solution (Doubly Linked List + HashMap):**
  - **HashMap** maps `Key -> LinkedListNode`. This gives $O(1)$ lookups.
  - **Doubly Linked List** allows us to detach any node from its current position and move it to the head in $O(1)$ time because each node has references to both `prev` and `next`.

#### Crucial Trade-offs to Discuss with the Interviewer

| Design Choice | Pros | Cons |
| :--- | :--- | :--- |
| **Virtual Nodes Scale** (e.g., 500 vnodes) | Excellent load balancing across servers. | Increased metadata footprint; lookup times on the ring ($O(\log(N \times Vnode\_Count))$) grow. |
| **No Replication (Partitioned Only)** | Maximizes total cluster storage capability. | If a node dies, all its cached data is lost (Cache Miss Storm on the Database). |
| **Active Replication (e.g., Sync Writes to Peer Nodes)** | Zero data loss on node failure. | Write path latency increases; introduces distributed consensus complexity. |

#### Interviewer Probes (The Tricky Questions)

**Q1: "What happens to your Consistent Hash Ring when a key becomes extremely hot (e.g., a viral celebrity profile)? Consistent Hashing will route 100% of that traffic to one node, crashing it. How do you mitigate this?"**
> **Answer:** We can use **Cache Layering** or **Query-string Decoration**. For ultra-hot keys, we can append a random salt to the key during reads/writes (e.g., `"viral_profile#1"`, `"viral_profile#2"`). This forces the consistent hash ring to distribute the hot key across multiple nodes. Alternatively, we can use a small, local "L1 cache" in-memory on our API Gateway layer to absorb queries to the most popular keys.

**Q2: "Under high concurrency, your LRU Cache's Linked List operations will suffer from lock contention. How do you scale write throughput?"**
> **Answer:** Standard LRU implementations protect pointers using a global lock, which kills performance on multi-core systems. To fix this, we can use **Segmented LRUs** (similar to Java's old `ConcurrentHashMap` segments), where we shard the keys across multiple internal LRU cache partitions to minimize lock contention. Alternatively, we can use an eviction library like **Caffeine** (which uses a ring buffer to record read/write operations asynchronously using a relaxed-ordering lock-free design).

---

### 4. ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Consistent Hashing solves the $\frac{1}{N}$ scaling problem:** When you scale your cache cluster from $N$ to $N+1$ nodes, traditional hashing (`key % N`) invalidates 100% of your cached data. Consistent Hashing ensures you only lose $\frac{1}{N}$ of your cache.
2. **LRU combines speed and ordering:** By pairing a **HashMap** (for $O(1)$ read/write access) with a **Doubly Linked List** (for $O(1)$ structural re-ordering), we achieve optimal eviction speeds.
3. **Virtual Nodes are mandatory:** Without them, consistent hashing suffers from high load variance across nodes. Virtual nodes act as statistical equalizers.

#### 💡 The Golden Rule
> **"Consistent Hashing decides *which* server gets the request; LRU decides *how long* that server keeps the data before throwing it away."**