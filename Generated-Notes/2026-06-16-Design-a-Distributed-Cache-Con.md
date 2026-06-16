---
title: High-Performance Distributed Caching: Consistent Hashing and LRU Eviction Architecture
date: 2026-06-16T10:32:02.147900
---

# High-Performance Distributed Caching: Consistent Hashing and LRU Eviction Architecture

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
A **Distributed Cache** is a system that pools the RAM of multiple computers (called **nodes**) to store frequently used data. By keeping data in-memory across a cluster, we avoid making slow, expensive queries to a central database. 

To make this work flawlessly at scale, we combine two computer science masterpieces:
1. **Consistent Hashing**: A smart mapping system that decides *which* computer gets to store a specific piece of data, ensuring that adding or removing computers doesn't throw the entire system into chaos.
2. **LRU (Least Recently Used) Eviction**: A boundary manager on *each individual computer* that automatically throws away the oldest, least-looked-at data when that computer runs out of memory.

### Real-World Analogy: The City-Wide Pizza Chain
Imagine a pizza chain with **4 kitchens (nodes)** scattered across a circular city bypass road, delivering pizzas to customers.

```
                  [Kitchen A]
             .  '             '  .
         .                           .
     [Kitchen D]                  [Kitchen B]
        .                             .
         .  '             '  .
                  [Kitchen C]
```

* **The Problem (Traditional Hashing)**: If you assigned deliveries strictly by your house number modulo the number of kitchens (`House_ID % 4`), and Kitchen D suddenly burned down, *everyone’s* assigned kitchen would change. Kitchen A would suddenly get Kitchen B’s old orders. Deliveries would grind to a halt because drivers wouldn't know the new routes.
* **The Solution (Consistent Hashing)**: Instead, you map every house and every kitchen to a location along the circular bypass road. If you order a pizza, it is made by the nearest kitchen clockwise from your house. If Kitchen D burns down, only the customers who were closest to D are affected; their orders simply route to the next kitchen clockwise (Kitchen A). Everyone else's kitchen stays exactly the same!
* **The Local Space Limit (LRU)**: Each kitchen only has space for 100 hot pizza boxes on their warming shelf. When the shelf is full, the chef throws away the cold pizza that was baked the longest time ago and hasn't been requested (Least Recently Used) to make room for a fresh, hot out-of-the-oven order.

### Why should I care?
If you build a web app today, a single cache server (like a standalone Redis instance) will eventually run out of RAM or CPU as your traffic grows. You need to partition (shard) your cache across 10, 50, or 1000 servers. Without consistent hashing, scaling your cache cluster up or down would invalidate almost 100% of your cached data, causing a massive stampede of traffic to your database, knocking it offline.

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Architectural Flow

```
+------------+             1. Hash(Key)              +---------------------------+
|   Client   | ------------------------------------> |   Consistent Hash Ring    |
+------------+                                       |                           |
      ^                                              |  Finds nearest node index |
      | 4. Return Data                               +---------------------------+
      |                                                            |
      |                                                            | 2. Route Request
      |                                                            v
      |                                              +---------------------------+
      +--------------------------------------------- |   Target Cache Node       |
                                                     |                           |
                                                     |  [Local LRU Cache Engine] |
                                                     |   - Check Map             |
                                                     |   - Update Linked List    |
                                                     +---------------------------+
```

### The Step-by-Step Mechanics

1. **Request Hashing**: A client requests data for the key `"user_992"`. The system hashes this key to a 32-bit integer (e.g., `185,220,110`).
2. **Ring Traversal**: The system looks at its circular list of server nodes (also mapped on the same 32-bit integer range) and finds the first node whose hash value is greater than or equal to `185,220,110`. Let’s say it's **Node B**.
3. **Local Node Execution**: The request is routed to Node B.
4. **Local LRU Check**: Node B checks its local memory:
   * **Cache Hit**: Node B finds `"user_992"`. It moves this key's memory node to the *head* (Most Recently Used position) of its local doubly linked list and returns the value to the client.
   * **Cache Miss**: It fetches the data from the database, stores it at the head of the linked list, and maps it in its hash map. If Node B is out of capacity, it deletes the item at the *tail* of the list (Least Recently Used) from both its memory and map.

### Code Implementation

Here is a complete, clean Python implementation featuring both the **Consistent Hash Ring** (routing) and the **LRU Cache** (local storage).

```python
import hashlib
import bisect
from typing import Optional, Dict

# ==========================================
# Component 1: The Local LRU Cache
# ==========================================

class ListNode:
    """A Node in a Doubly Linked List."""
    def __init__(self, key: str, value: str):
        self.key = key
        self.val = value
        self.prev: Optional[ListNode] = None
        self.next: Optional[ListNode] = None

class LRUCache:
    """Thread-unsafe LRU Cache implementation for single-node caching."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.map: Dict[str, ListNode] = {}
        # Sentinel dummy nodes to avoid null-pointer checks during list mutation
        self.head = ListNode("", "")
        self.tail = ListNode("", "")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: ListNode):
        """Removes a node from its current position in the Doubly Linked List."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_head(self, node: ListNode):
        """Inserts a node right after the dummy head (Most Recently Used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: str) -> Optional[str]:
        if key in self.map:
            node = self.map[key]
            self._remove(node)
            self._add_to_head(node)  # Mark as recently used
            return node.val
        return None

    def put(self, key: str, value: str):
        if key in self.map:
            self._remove(self.map[key])
        
        new_node = ListNode(key, value)
        self._add_to_head(new_node)
        self.map[key] = new_node
        
        if len(self.map) > self.capacity:
            # Evict Least Recently Used (node right before dummy tail)
            lru_node = self.tail.prev
            self._remove(lru_node)
            del self.map[lru_node.key]


# ==========================================
# Component 2: Consistent Hash Ring
# ==========================================

class ConsistentHashRing:
    """Distributes keys across multiple virtual/physical nodes."""
    def __init__(self, replicas: int = 3):
        self.replicas = replicas  # Number of virtual nodes per physical node
        self.ring = []            # Sorted list of virtual node hashes
        self.hash_to_node = {}    # Map: Virtual Node Hash -> Physical Node Name

    def _hash(self, key: str) -> int:
        """MD5 Hash converted to an integer range [0, 2^128 - 1]."""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)

    def add_node(self, node: str):
        """Adds a physical node by placing multiple virtual nodes on the ring."""
        for i in range(self.replicas):
            vnode_name = f"{node}#vnode_{i}"
            val = self._hash(vnode_name)
            bisect.insort(self.ring, val) # Maintains sorted order
            self.hash_to_node[val] = node

    def remove_node(self, node: str):
        """Removes a physical node from the ring."""
        for i in range(self.replicas):
            vnode_name = f"{node}#vnode_{i}"
            val = self._hash(vnode_name)
            idx = bisect.bisect_left(self.ring, val)
            if idx < len(self.ring) and self.ring[idx] == val:
                del self.ring[idx]
                del self.hash_to_node[val]

    def get_node(self, key: str) -> str:
        """Finds the closest clockwise physical node for a given key."""
        if not self.ring:
            raise ValueError("The hash ring is empty!")
        
        val = self._hash(key)
        # Binary search the sorted ring
        idx = bisect.bisect_right(self.ring, val)
        
        # If the hash is larger than all elements, wrap around to index 0
        if idx == len(self.ring):
            idx = 0
            
        return self.hash_to_node[self.ring[idx]]


# ==========================================
# Execution Simulation
# ==========================================
if __name__ == "__main__":
    # 1. Initialize our cache cluster nodes
    nodes = ["Node-A", "Node-B", "Node-C"]
    cluster = {node: LRUCache(capacity=2) for node in nodes}
    
    # 2. Initialize Consistent Hash Ring
    ring = ConsistentHashRing(replicas=3)
    for node in nodes:
        ring.add_node(node)
        
    # 3. Write data to the cluster
    keys_to_store = {"user_1": "Alice", "user_2": "Bob", "user_3": "Charlie", "user_4": "Diana"}
    for key, val in keys_to_store.items():
        target_node = ring.get_node(key)
        cluster[target_node].put(key, val)
        print(f"Key '{key}' routed and stored in: {target_node}")
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic Under the Hood

#### 1. Why Virtual Nodes (VNodes)?
In a basic consistent hashing ring, if you map only 3 physical nodes (`Node-A`, `Node-B`, `Node-C`), they might hash to positions very close to each other. This causes **non-uniform distribution** (hotspots), where one node gets 80% of the keys, while others sit idle. 

By mapping each physical node to multiple **Virtual Nodes** (e.g., `Node-A#1`, `Node-A#2`, ..., `Node-A#200`) across the ring, the nodes are interleaved and randomly shuffled. Statistically, this guarantees a highly uniform distribution of keys across the entire hardware pool.

#### 2. The Mechanics of $O(1)$ LRU
An LRU cache cannot rely on a simple array or a pure hash map:
* An **array** requires $O(N)$ shifts on updates/deletions.
* A **hash map** has no concept of sequence or order.

By combining a **Hash Map** and a **Doubly Linked List (DLL)**, we achieve absolute $O(1)$ complexity for both lookups and mutations:
* The Map stores `{Key -> Pointer to DLL Node}`.
* When a key is accessed, we use the map pointer to directly target the DLL node, detach it, and append it to the Head in $O(1)$ time.

```
       Hash Map
+--------------------+
| "user_1" | Pointer | -----------------------+
+----------+---------+                        |
                                              v
                                       Doubly Linked List
                      +-------------------------------------------------+
                      | Dummy Head <-> [Node_1] <-> [Node_2] <-> Dummy Tail |
                      +-------------------------------------------------+
```

#### 3. Concurrency & Locking Overhead
In high-throughput environments, multiple client threads read/write to the cache simultaneously.
* **Problem**: Standard Doubly Linked List operations are not thread-safe. A race condition can easily corrupt pointers, causing infinite loops or segmentation faults.
* **Mitigation**: Using a heavy global lock on the LRU engine (e.g., a mutex or `synchronized` block in Java) ruins concurrency because threads have to wait in line to update the access order. To scale, high-performance engines use **Segmented Locks** (like Java's `ConcurrentHashMap`) or lock-free concurrency queues (using CAS - Compare-And-Swap operations) to track read actions asynchronously.

---

### Trade-offs
* **Faster Lookup vs. Higher Memory Footprint**: The DLL requires storing two pointers (`prev` and `next`) per element. On a 64-bit system, that's 16 bytes of metadata overhead per cache entry. For millions of keys, this overhead adds up to gigabytes of pure memory overhead.
* **Replication Cost (CAP Theorem)**: If you replicate cached data to secondary nodes to prevent data loss on node failure, you face a trade-off: do you write synchronously to replicas (low performance, high consistency) or asynchronously (high performance, potential stale reads)?

---

### Interviewer Probes & Counter-Strategies

#### 🎙️ Probe 1: "Consistent Hashing prevents total invalidation when scaling. But what if a node fails? During the time the system updates its ring, won't the database get hammered by a Cache Stampede?"
* **Answer**: Yes. When a node dies, all requests routed to it immediately miss and fall back to the DB simultaneously. To prevent this, implement **Cache Warm-up / Passive replication**, where each key is written to the primary node and the next sequential node clockwise on the ring. Additionally, use **Single-flight / Mutex locking** at the application tier—only allow the first thread that missed the cache to query the database, while other concurrent threads wait for that single thread to populate the cache and broadcast the result.

#### 🎙️ Probe 2: "What if one key is exceptionally hot (e.g., a celebrity profile page)? Even with consistent hashing and virtual nodes, all requests for that specific key go to a single node, overloading it. How do you solve this?"
* **Answer**: To mitigate "hotkeys", we can implement:
  1. **Query-side Salting**: Append a random suffix (e.g., `celebrity_123_#1`, `celebrity_123_#2`) to the key on write, scattering duplicates of the hot data to different nodes on the ring. The client then randomly picks a suffix on read to load-balance requests.
  2. **L1 Local Cache**: Keep a tiny, short-lived (e.g., 5-second TTL) cache locally on the client or API gateway level to serve extremely popular read-only assets before they even reach the distributed cache layer.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Consistent Hashing avoids total cache loss**: Adding or removing $M$ nodes in a cluster of $N$ nodes only invalidates $\frac{M}{N}$ of the keys, rather than 100% of them.
2. **Virtual Nodes are mandatory**: They eliminate "skewed data distribution" by spreading virtual representations of physical hardware evenly across the hash ring.
3. **LRU combines Dict + Doubly Linked List**: Hash Map provides fast search ($O(1)$); the Doubly Linked List provides fast order updates and eviction ($O(1)$).

### 1 Golden Rule
> **"Minimize re-shuffling at scale with Consistent Hashing; maximize memory utility at the node level with LRU."**