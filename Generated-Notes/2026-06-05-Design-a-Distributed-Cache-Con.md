---
title: Distributed Cache Architecture: Seamless Scaling with Consistent Hashing and Local LRU Eviction
date: 2026-06-05T10:31:48.714123
---

# Distributed Cache Architecture: Seamless Scaling with Consistent Hashing and Local LRU Eviction

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
A **Distributed Cache** is a system that keeps frequently accessed data in ultra-fast RAM spread across multiple servers. 

To build one that can scale to handle millions of requests per second, we must solve two critical problems:
1. **The Routing Problem (Consistent Hashing):** When a client asks for a piece of data (e.g., user profile info), how do we know *which* server holds that data without asking every single server in the cluster?
2. **The Space Problem (LRU Eviction):** Ram is expensive and limited. When a single cache server runs out of memory, how does it gracefully throw away old data to make room for new data?

#### A Real-World Analogy
Imagine a massive global chain of specialized libraries. 
* **Consistent Hashing** is the centralized indexing system. Instead of every library storing every book (which is too expensive), the system maps book titles to specific library branches. If you open a new library branch, you don't pack up and move all the books in the world; you only move a small shelf of books from the neighboring libraries to the new one.
* **LRU (Least Recently Used) Eviction** is the display table at the front of each individual library. This table can only hold 100 books. When a reader asks for a book, the librarian fetches it. If it’s not on the display table, they get it from the deep archives (the database), place it on the table, and kick the book that hasn't been touched in the longest time off the table back to the archives.

#### Why should you care?
If you simply route traffic using standard hashing (like `hash(key) % number_of_servers`), adding or removing a single server will change the destination of **almost 99% of your keys**. This causes a "cache stampede" where all requests suddenly miss the cache and hit your database at once, knocking your entire infrastructure offline. Consistent Hashing solves this, ensuring that adding a server only affects a tiny fraction of your keys ($1/N$).

---

### 2. 🛠️ How it Works (Step-by-Step)

#### The Workflow
1. **The Hash Ring:** We visualize our 32-bit hash space (from $0$ to $2^{32} - 1$) as a circular ring.
2. **Server Registration:** We hash each server's identifier (e.g., IP address) and place it at a specific position on this circular ring.
3. **Key Lookup:** When a request for key `"user_99"` arrives, we hash `"user_99"`. We then travel clockwise along the ring until we encounter the first server. That server is designated to hold that key.
4. **Local Storage (LRU):** Once the request reaches that server, it looks up its local memory. If it's a miss, it fetches it from the database, stores it in its local LRU cache (evicting the oldest item if full), and returns it to the client.

```
                  Hash Ring (0 to 2^32 - 1)
                     
                       [Server A] (Hash: 100,000)
                        /      \
                       /        \  <-- Key "user_99" (Hash: 150,000)
                      /          \     Routes clockwise to Server B
         [Server C]  |            |  
  (Hash: 3,000,000)  |            |  [Server B] (Hash: 2,000,000)
                      \          /
                       \        /
                        \      /
                    Virtual Nodes (VNodes) 
             spread physical servers across the ring 
                  to balance the data load.
```

#### The Code Implementation (Python)
Here is a complete, runnable simulation of a Distributed Cache coordinator using a **Consistent Hash Ring with Virtual Nodes** routing to local **LRU Cache** nodes.

```python
import hashlib
import bisect
from collections import OrderedDict

class LRUCache:
    """A thread-safe-ready local Least Recently Used (LRU) Cache."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()  # Keeps track of insertion/access order

    def get(self, key: str) -> str:
        if key not in self.cache:
            return None
        # Move the accessed key to the end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: str) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            # Pop the first item (least recently used)
            self.cache.popitem(last=False)


class DistributedCacheCoordinator:
    """Manages routing keys to physical cache nodes via Consistent Hashing."""
    def __init__(self, replica_count: int = 3):
        self.replica_count = replica_count  # Number of virtual nodes per physical node
        self.ring = []       # Sorted list of virtual node hash values
        self.vnode_map = {}  # Map from vnode hash -> physical node name (e.g., "Server-1")
        self.nodes = {}      # Map from physical node name -> LRUCache instance

    def _hash(self, key: str) -> int:
        """Returns a 32-bit integer hash of the key."""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16) & 0xFFFFFFFF

    def add_node(self, node_name: str, capacity: int) -> None:
        """Adds a physical node to the ring, generating virtual nodes."""
        self.nodes[node_name] = LRUCache(capacity)
        for i in range(self.replica_count):
            vnode_key = f"{node_name}-vnode-{i}"
            vnode_hash = self._hash(vnode_key)
            # Insert maintaining sorted order
            bisect.insort(self.ring, vnode_hash)
            self.vnode_map[vnode_hash] = node_name

    def remove_node(self, node_name: str) -> None:
        """Removes a physical node and its virtual nodes from the ring."""
        if node_name not in self.nodes:
            return
        del self.nodes[node_name]
        for i in range(self.replica_count):
            vnode_key = f"{node_name}-vnode-{i}"
            vnode_hash = self._hash(vnode_key)
            self.ring.remove(vnode_hash)
            del self.vnode_map[vnode_hash]

    def _get_node_name(self, key: str) -> str:
        """Finds the closest physical node on the ring clockwise."""
        if not self.ring:
            return None
        key_hash = self._hash(key)
        # Binary search to find the clockwise index on the ring
        idx = bisect.bisect_right(self.ring, key_hash)
        # If the hash is larger than all elements on the ring, wrap around to index 0
        if idx == len(self.ring):
            idx = 0
        return self.vnode_map[self.ring[idx]]

    def get(self, key: str) -> str:
        node_name = self._get_node_name(key)
        if not node_name:
            return None
        return self.nodes[node_name].get(key)

    def put(self, key: str, value: str) -> None:
        node_name = self._get_node_name(key)
        if node_name:
            self.nodes[node_name].put(key, value)


# --- Quick verification ---
if __name__ == "__main__":
    # Create coordinator with 3 virtual nodes per server
    coordinator = DistributedCacheCoordinator(replica_count=3)
    coordinator.add_node("Server-A", capacity=2)
    coordinator.add_node("Server-B", capacity=2)

    # Put some data
    coordinator.put("user_1", "Alice")
    coordinator.put("user_2", "Bob")
    coordinator.put("user_3", "Charlie")

    # Access data
    print(f"User 1 is on {coordinator._get_node_name('user_1')}: {coordinator.get('user_1')}")
    print(f"User 2 is on {coordinator._get_node_name('user_2')}: {coordinator.get('user_2')}")
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Inner Mechanics
To excel in a senior-level interview, you must articulate the physical-to-virtual node relationship and the structural layout of the LRU cache.

```
LRU Cache Inner Design:
+--------------------------------------------------------------+
|                          Hash Map                            |
|  { "user_1": NodeA, "user_2": NodeB, "user_3": NodeC }       |
+--------------------------------------------------------------+
                                 | (Points to Doubly Linked List nodes)
                                 v
   [Head] <-> [NodeA (user_1)] <-> [NodeB (user_2)] <-> [Tail]
```

* **The LRU Double-Data-Structure:** An LRU cache cannot be built efficiently with just a List or just a Map. It is a composite data structure.
  * **Hash Map:** Provides $O(1)$ lookups to check if an item exists.
  * **Doubly Linked List:** Provides $O(1)$ updates to re-order nodes when they are accessed, and $O(1)$ deletions from both the head (oldest/eviction target) and tail (newest/most recently used).
* **Virtual Nodes (Vnodes):** Why use them? Without Vnodes, physical servers are hashed to arbitrary positions on the ring. This results in **unbalanced load distribution** (one node might be responsible for 70% of the ring space). By creating $V$ virtual nodes for every physical node (e.g., $V=256$), we slice the ring into hundreds of tiny, interleaved segments. Statistically, this guarantees an even load distribution across all machines (a deviation of $<5\%$).

#### Trade-offs & Limitations
* **Memory Overhead of Metadata:** While LRU guarantees $O(1)$ runtime, every entry requires a Hash Map bucket and two node pointers (`prev` and `next`). On 64-bit systems, pointers take 8 bytes each. For millions of tiny keys, the memory overhead of the pointers and the map structure can actually exceed the size of the cached data itself.
* **Consistency vs. Availability (CAP Theorem):** When a cache node goes down, the keys assigned to it will naturally fall to the next node on the ring. The next node won't have this data, causing temporary cache misses (AP - Availability prioritized over Consistency). If strong consistency is needed, we must implement replication (e.g., writing keys to $N$ consecutive nodes along the ring).

---

#### Interviewer Probes (Tricky Questions & Counter-Strategies)

##### Probe 1: *"Your local LRU cache works great in a single thread. But in a high-concurrency environment, the Doubly Linked List pointers are protected by a global mutex lock. This creates a severe lock contention bottleneck. How do you scale this?"*
* **The Pitch:** "To bypass global lock contention on the Doubly Linked List, we can employ two strategies:
  1. **Segmented LRU / Cache Sharding:** We split the single LRU cache on the node into $N$ independent sharded LRU caches (e.g., 16 segments) based on the hash of the key. Each segment has its own lock, reducing contention by $16\times$.
  2. **Page-Replacement Approximations (like Clock-Pro or 2Q):** Instead of moving a node on the Doubly Linked List every single time it is read (which requires a write lock), we can use a **read buffer** or use a **Clock (Second Chance) Algorithm** which only updates a single bit atomically. This converts a structural pointer write operation into a simple, lock-free atomic bit flip."

##### Probe 2: *"What happens to the Consistent Hash Ring when there is a transient network partition? How do you prevent split-brain issues?"*
* **The Pitch:** "In a network partition, some clients might see Server A as dead, while other clients can still talk to it. This leads to dual writes and split-brain states. To handle this:
  1. We can implement a **gossip protocol** (like SWIM) among nodes to establish a decentralized consensus on which nodes are alive.
  2. We can pair Consistent Hashing with **active anti-entropy** using **Merkle Trees** (cryptographic trees of key hashes). When a node recovers or partitions heal, nodes can rapidly compare their Merkle trees to detect missing or mismatched keys and sync up without scanning the entire dataset."

##### Probe 3: *"How do we handle 'Hotspots' (e.g., a single celebrity's profile key that receives 100,000 requests/sec)? Consistent hashing will still route 100% of this traffic to a single node."*
* **The Pitch:** "Consistent hashing solves the *distribution of key space*, but it doesn't solve *skewed read access patterns*. To mitigate hotkeys:
  1. **Local Query Buffering / L1 Cache:** We can implement a micro-cache (in-process memory of the API gateways) with a very short TTL (e.g., 1 second) specifically for heavily requested read keys.
  2. **Consistent Hash Replication:** We can write hotkeys to the primary node and its next $R$ clockwise neighbors on the ring. Read requests can randomly query any of these $R$ neighbors to balance the load."

---

### 4. ✅ Summary Cheat Sheet

```
+---------------------------------------------------------------------------------+
|                       DISTRIBUTED CACHE SYSTEM SUMMARY                          |
+---------------------------------------------------------------------------------+
|   COMPONENT          |  PRIMARY DATA STRUCTURES   |  CORE GOAL                  |
|----------------------+----------------------------+-----------------------------|
|   Consistent Ring    |  Balanced Binary Tree /    |  Route keys to nodes with   |
|                      |  Sorted Array + VNodes     |  minimal data movement.     |
|----------------------+----------------------------+-----------------------------|
|   Local Cache        |  HashMap +                 |  Bound local RAM memory with|
|                      |  Doubly Linked List        |  strict O(1) eviction.      |
+---------------------------------------------------------------------------------+
```

#### 3 Key Takeaways
1. **Consistent Hashing scales horizontally** because adding/removing servers only requires moving $1/N$ of the total keys, preventing database meltdowns during cluster scaling.
2. **Virtual Nodes are mandatory** to prevent load skew. They ensure that physical servers are mapped uniformly across the mathematical hash ring.
3. **The classic LRU Cache is a composite structure**: The Hash Map provides $O(1)$ search, while the Doubly Linked List provides $O(1)$ ordering and eviction.

#### 1 Golden Rule
> *"Consistent Hashing scales your cluster horizontally without losing state; LRU manages your node's local memory footprint vertically without losing performance."*