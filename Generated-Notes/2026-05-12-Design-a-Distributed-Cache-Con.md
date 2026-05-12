---
title: Distributed Cache: Balancing Load with Consistent Hashing and LRU
date: 2026-05-12T10:31:38.306491
---

# Distributed Cache: Balancing Load with Consistent Hashing and LRU

1. 💡 The "Big Picture" (Plain English)
### What is this in simple terms?
Imagine you run a global pizza chain. You have thousands of orders coming in. You can’t keep every pizza ready in one single kitchen—it would explode. So, you have ten different kitchens (nodes). 

**Consistent Hashing** is the "Dispatcher" who decides which kitchen handles which pizza order based on the pizza's name (the key). 
**LRU (Least Recently Used)** is the "Kitchen Counter" manager. Each kitchen only has space for 50 pizzas. When the counter is full and a new order comes in, the manager throws away the pizza that hasn't been touched in the longest time.

### Why should I care?
In the digital world, if your app gets a million hits a second, a single database will melt. You need a Distributed Cache.
- **Consistent Hashing** ensures that if you add a new server, you don't have to rearrange your entire database (re-mapping everything).
- **LRU** ensures your servers don't run out of RAM by intelligently discarding "cold" data to make room for "hot" data.

---

2. 🛠️ How it Works (Step-by-Step)

### The Workflow:
1.  **The Request:** A user asks for data (e.g., `user_id: 101`).
2.  **The Ring:** We hash `101` to a number. We look at a "Hash Ring" and find the first server sitting clockwise from that number.
3.  **The Local Check:** We go to that specific server. That server looks at its local **LRU Cache**.
4.  **Hit or Miss:** 
    *   **Hit:** Return data and move `101` to the "Most Recently Used" position.
    *   **Miss:** Fetch from DB, store it in the LRU (potentially kicking out an old item), and return.

### The Flow:
```text
[Client] -> [Hash(Key)] -> [Find Node on Ring] -> [Node X: LRU Cache] -> [Result]
                                                        |
                                                  (If Miss: Fetch DB)
```

### Clean Code Implementation (Conceptual Python):
```python
import hashlib
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.cache = OrderedDict() # Maintains order of insertion
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache: return None
        self.cache.move_to_end(key) # Mark as recently used
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache: self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False) # Evict Least Recently Used

class DistributedCache:
    def __init__(self, nodes, lru_size):
        # The "Ring" (Sorted list of hashes of node names)
        self.ring = sorted([self._hash(n) for n in nodes])
        self.node_map = {self._hash(n): LRUCache(lru_size) for n in nodes}

    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_node(self, key):
        h = self._hash(key)
        # Find the first node in the ring >= h (Clockwise)
        for node_hash in self.ring:
            if h <= node_hash: return self.node_map[node_hash]
        return self.node_map[self.ring[0]] # Wrap around

    def pick(self, key):
        node = self.get_node(key)
        return node.get(key)
```

---

3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic: Virtual Nodes (VNodes)
Standard Consistent Hashing has a flaw: nodes might be distributed unevenly on the ring, leading to "Hotspots" (one server doing all the work). 
**The Solution:** We assign each physical server multiple **Virtual Nodes** (e.g., Server A maps to `A_1`, `A_2`, `A_3` on the ring). This blurs the lines and ensures that if a server fails, its load is distributed evenly across *all* other servers, not just its immediate neighbor.

### The Trade-offs
*   **Memory vs. Accuracy:** A larger LRU capacity means fewer DB hits (higher hit rate) but costs more in RAM.
*   **The "Thundering Herd" Problem:** When a very popular key expires from the LRU, multiple clients might see the "Miss" at the exact same time and all try to write to the DB simultaneously. 
    *   *Mitigation:* Use "Lease" or "Soft TTL" where the first request triggers the refresh while others receive slightly stale data for a few milliseconds.

### Interviewer Probes
1.  **"What happens to the LRU when a node crashes?"** 
    *   *Answer:* In a simple setup, that cache is lost. Consistent Hashing will route requests to the next node. However, for high availability, we often use **Replication Factors**. The key is stored in the LRU of Node N *and* Node N+1.
2.  **"Why use a Doubly Linked List for LRU?"**
    *   *Answer:* A Hashmap gives us $O(1)$ lookup, but it doesn't track order. A Doubly Linked List allows us to move an element to the "front" or delete from the "back" in $O(1)$ time. Combined, they create the perfect LRU.
3.  **"How do you handle a 'Hot Key' that overwhelms a single node?"**
    *   *Answer:* If Justin Bieber tweets, Consistent Hashing will always send that request to the same node. We solve this by implementing **Local L1 Caching** (a tiny, short-lived cache on the application server itself) to protect the Distributed Cache.

---

4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1.  **Consistent Hashing** minimizes data movement when the cluster size changes (only $K/N$ keys move).
2.  **Virtual Nodes** are essential to prevent one server from getting slammed while others stay idle.
3.  **LRU Cache** is the local gatekeeper, ensuring we prioritize "Hot Data" and keep memory usage predictable.

### 💡 The Golden Rule
> **Consistent Hashing decides WHERE the data lives; LRU decides HOW LONG it stays there.**