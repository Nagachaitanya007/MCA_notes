---
title: Distributed Cache Internals: Implementing Key-to-Node Ring Routing and O(1) Memory Eviction
date: 2026-08-01T10:32:20.405568
---

# Distributed Cache Internals: Implementing Key-to-Node Ring Routing and O(1) Memory Eviction

---

### 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
A **Distributed Cache** is a system that spreads temporary, fast-access data across multiple server nodes instead of relying on a single machine's memory. 

To build one successfully, two core algorithms work together:
1. **Consistent Hashing**: Determines **which server** in the network holds a specific key.
2. **LRU (Least Recently Used) Eviction**: Manages memory **inside that specific server**, kicking out old, unused data when space runs out.

#### Real-World Analogy: The Regional Library Network
Imagine a regional library network spread across 5 neighboring towns. 

* **Consistent Hashing** is the **central catalog rulebook**. When you search for a book title (a key), the rulebook uses the title's name to instantly point you to the exact town library branch (the node) holding that book. If a town library closes down, the rulebook maps its books to the next nearest library branch without rearranging the entire regional catalog.
* **LRU Eviction** is the **shelf-management policy** inside each branch. Each library branch has limited shelf space. When a new book arrives and shelves are full, the librarian looks at the return log and discards the book that hasn't been checked out for the longest time (the least recently used item).

```
   [ Client Request: key = "user_42" ]
                   │
                   ▼
      ┌─────────────────────────┐
      │   Consistent Hashing    │ ──► "Which server node gets this key?"
      └────────────┬────────────┘     (Answer: Node B)
                   │
                   ▼
       ┌───────────────────────┐
       │     Server Node B     │
       │ ┌───────────────────┐ │
       │ │   Local LRU Cache │ │ ──► "Memory full? Evict least recently used!"
       │ └───────────────────┘ │
       └───────────────────────┘
```

#### Why should I care?
* **Single-Server Bottlenecks**: A single cache server (like a basic Redis or Memcached instance) will eventually run out of RAM or network bandwidth.
* **Naive Scaling Breaks**: If you distribute keys using simple modulo hashing (`hash(key) % N_servers`), adding or removing **one server** changes `N`, which remaps ~99% of your keys. This wipes out your cache hit rate overnight, triggering a catastrophic load surge on your database (a **cache stampede**).
* **Memory Exhaustion**: Without eviction policies, servers crash due to Out-Of-Memory (OOM) errors.

---

### 🛠️ How it Works (Step-by-Step)

#### Step-by-Step Request Lifecycle

1. **Hash the Key to a Ring Position**:
   The client or proxy runs the key (e.g., `"user_99"`) through a uniform hash function (like MurmurHash3) to produce a 32-bit integer. This integer maps to a point on a conceptual ring $[0 \text{ to } 2^{32}-1]$.

2. **Route to the Closest Node (Clockwise)**:
   The routing layer searches the ring clockwise to find the first physical server (or virtual node) whose position is $\ge$ the key's hash value.

3. **Execute Local LRU Operations**:
   The request arrives at the designated node:
   * **GET**: Read from the local HashMap. Move the accessed node to the **head** of a Doubly Linked List (marking it most recently used).
   * **PUT**: Insert into the HashMap and place at the head of the Doubly Linked List. If memory exceeds max capacity, drop the node at the **tail** of the list (the least recently used item) and remove its key from the HashMap.

---

#### Clean Implementation (Python)

```python
import hashlib
import bisect

# -------------------------------------------------------------
# 1. NODE-LEVEL LRU EVICTION ENGINE
# -------------------------------------------------------------
class DListNode:
    def __init__(self, key: str, val: str):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None

class LRUCacheNode:
    """Standard O(1) LRU Cache using HashMap + Doubly Linked List."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.lookup = {} # Key -> DListNode
        
        # Sentinel Head and Tail nodes to prevent null checks
        self.head = DListNode("", "")
        self.tail = DListNode("", "")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: DListNode):
        """Unlink node from the list."""
        p, n = node.prev, node.next
        p.next = n
        n.prev = p

    def _add_to_head(self, node: DListNode):
        """Insert node immediately after sentinel head."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: str) -> str:
        if key not in self.lookup:
            return None
        node = self.lookup[key]
        self._remove(node)
        self._add_to_head(node)  # Mark as recently used
        return node.val

    def put(self, key: str, val: str):
        if key in self.lookup:
            self._remove(self.lookup[key])
        
        new_node = DListNode(key, val)
        self._add_to_head(new_node)
        self.lookup[key] = new_node

        if len(self.lookup) > self.capacity:
            # Evict LRU element from tail
            lru = self.tail.prev
            self._remove(lru)
            del self.lookup[lru.key]

# -------------------------------------------------------------
# 2. CLUSTER ROUTING ENGINE (CONSISTENT HASHING RING)
# -------------------------------------------------------------
class ConsistentHashRing:
    def __init__(self, num_replicas: int = 3):
        self.num_replicas = num_replicas # Virtual nodes per physical server
        self.ring_keys = []              # Sorted array of hash values
        self.ring_map = {}               # Hash value -> Physical Server Node instance

    def _hash(self, key: str) -> int:
        """32-bit Integer Hash value generated by MD5."""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16) & 0xFFFFFFFF

    def add_node(self, node_id: str, capacity: int):
        """Adds a physical node to the ring using Virtual Nodes."""
        node_instance = LRUCacheNode(capacity)
        for i in range(self.num_replicas):
            vnode_key = f"{node_id}#vnode-{i}"
            h_val = self._hash(vnode_key)
            self.ring_map[h_val] = node_instance
            bisect.insort(self.ring_keys, h_val)

    def get_node(self, key: str) -> LRUCacheNode:
        """Finds the responsible server node using Clockwise Search."""
        if not self.ring_keys:
            return None
        h_val = self._hash(key)
        # Binary search for the first node with hash >= key's hash
        idx = bisect.bisect_right(self.ring_keys, h_val)
        if idx == len(self.ring_keys):
            idx = 0  # Wrap around to start of the ring
        return self.ring_map[self.ring_keys[idx]]

# Usage Example:
# ring = ConsistentHashRing(num_replicas=100)
# ring.add_node("node-A", capacity=2)
# ring.add_node("node-B", capacity=2)
# node = ring.get_node("user_session_123")
# node.put("user_session_123", "data_payload")
```

---

### 🧠 The "Deep Dive" (For the Interview)

#### 1. The Mechanics: Virtual Nodes (VNodes)
Under basic consistent hashing, hashing a server's IP address maps physical servers to sparse points on the ring. This causes two critical issues:
* **Non-Uniform Load Distribution**: Server A might own 70% of the ring key space while Server B owns only 30%.
* **Cascading Failures**: If Server A fails, 100% of its key space transfers to its immediate clockwise neighbor, often causing the neighbor to crash under sudden overload.

**Solution**: Map every physical server to multiple **Virtual Nodes** (e.g., 100–250 per physical server). Instead of mapping `NodeA` to one point, we place `NodeA#1`, `NodeA#2`, ..., `NodeA#200` randomly around the ring. 

When a physical server is added or removed, its workload is evenly distributed across *all* remaining active machines.

```
                  [ Virtual Node Ring ]
                  
                    NodeA#0 (0x2A)
                   /              \
         NodeC#1 (0xE0)          NodeB#0 (0x4F)
             |                        |
         NodeB#1 (0xA1)          NodeC#0 (0x7C)
                   \              /
                    NodeA#1 (0x8F)
```

---

#### 2. Local LRU Concurrency Bottlenecks & Approximations

In multi-threaded environments (like Java JVM or C++ multi-threaded nodes), standard $O(1)$ LRU with a Doubly Linked List suffers from **heavy lock contention**. 

* **The Problem**: Every `GET` operation updates the list structure to move the accessed item to the head. This converts safe concurrent read paths into structural write operations, requiring exclusive locks (`ReentrantLock` or `synchronized`).
* **The Production Fix (Sampled/Approximated LRU)**: Redis and production caches skip the linked list completely to maximize throughput. Instead:
  1. Each cached item stores a 24-bit **last accessed timestamp**.
  2. When memory limit is reached, the server samples $N$ random keys (e.g., $N=5$) and evicts the one with the oldest timestamp.
  3. This drastically cuts lock overhead while maintaining ~98% eviction efficiency compared to exact LRU.

---

#### 3. Key Trade-offs

| Strategy / Feature | Advantage | Trade-off / Cost |
| :--- | :--- | :--- |
| **Consistent Hashing (with VNodes)** | Minimal key remapping ($K/N$) during scale events; eliminates cache stampedes. | Increased memory footprint to maintain ring routing metadata on clients/proxies; $O(\log(\text{VNodes}))$ lookup complexity via Binary Search. |
| **Exact LRU (HashMap + LinkedList)** | Predictable, deterministic $O(1)$ evictions; guarantees strict eviction order. | Read operations require writes (moving nodes to head), creating severe multi-threaded lock contention. |
| **Sampled/Approximated LRU** | Zero node-relinking penalty; high read throughput; low concurrency overhead. | Probabilistic eviction—occasionally evicts slightly newer items instead of strict absolute oldest. |

---

#### 4. Interviewer Probes & Follow-Up Questions

##### Probe 1: "How do you handle a 'Hotspot Key' (e.g., a viral post requested by millions of users simultaneously)?"
* **Why it's a trap**: Consistent hashing *always* maps a specific key to the exact same node regardless of how many Virtual Nodes you have. VNodes balance node capacity, not single-key popularity spikes.
* **Senior Solution**: 
  1. **Key Prefixing/Splitting**: Append random numbers to hot keys (e.g., `hot_key#1`, `hot_key#2`, ..., `hot_key#N`), spreading reads across multiple ring locations.
  2. **Near-Cache (Client-Side Caching)**: Use local memory inside the application client instances for hot keys with short TTLs (e.g., 5 seconds).

##### Probe 2: "What happens when a node goes down mid-operation? How do you prevent stale reads?"
* **Senior Solution**: Discuss **Replication Factor ($R$)** and **Quorum Writes/Reads**:
  * Instead of mapping a key to a single node, store it on the primary node *and* its next $R-1$ distinct physical clockwise neighbors on the ring.
  * Use a Gossip Protocol (e.g., Dynamo DB style) or Zookeeper to detect dead nodes and trigger ring state updates across proxies.

##### Probe 3: "Why choose MurmurHash3 or FNV-1a over MD5/SHA-256 for consistent hashing rings?"
* **Senior Solution**: Cryptographic hashes (MD5/SHA-256) are computationally expensive and slow down ring lookups. Non-cryptographic hashes like **MurmurHash3** provide excellent bit dispersion and uniform distribution across the 32-bit or 64-bit integer space while executing orders of magnitude faster.

---

### ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Consistent Hashing avoids catastrophic cache stampedes**: Only $1/N$ keys move when nodes enter or exit a cluster of size $N$, compared to ~100% with modulo hashing.
2. **Virtual Nodes are mandatory in production**: Without them, keys group unevenly and node failures cause cascading downstream outages.
3. **Pure LRU causes lock contention**: Exact LRU mutates a linked list on every `GET`. High-throughput distributed nodes often use **Sampled LRU** or **Segmented LRU (2Q)** instead.

#### 1 "Golden Rule" to Remember
> **"Consistent Hashing routes the key across the cluster boundary; LRU manages the space within the host boundary."**