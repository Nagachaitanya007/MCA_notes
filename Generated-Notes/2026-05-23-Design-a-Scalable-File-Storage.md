---
title: S3 Storage Node Internals: Append-Only Engines and CDN Cache Coherency
date: 2026-05-23T10:31:39.402852
---

# S3 Storage Node Internals: Append-Only Engines and CDN Cache Coherency

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
When you upload a file to an object storage system like Amazon S3, two massive engineering challenges happen behind the scenes:
1. **At the Storage Node level:** How does a single physical server write billions of files to its hard drives instantly without choking, wearing out the disk, or losing track of where files are?
2. **At the Global Edge level (CDN):** When you overwrite or delete a file, how does a caching server on the other side of the world instantly know to stop serving the old version without slowing down your users?

### A Real-World Analogy
Imagine a massive shipping warehouse:
* **The Storage Node is a clerk with a notebook.** Instead of constantly erasing, shifting, and reorganizing files on shelves (which takes forever), the clerk writes every incoming package down at the absolute bottom of a continuous ledger book (**Append-Only Log**). To find a package instantly, the clerk keeps a deck of index cards in their shirt pocket (**In-Memory Index**) showing the exact page and line number where that package is recorded.
* **The CDN is a local corner store.** To serve customers faster, the corner store keeps photocopies of the warehouse's most popular items. If the warehouse updates an item, it doesn't wait for the corner store's photocopy to turn yellow and expire (**TTL**). Instead, it immediately sends a courier to rip up the old photocopy (**Active Cache Invalidation**).

### Why should I care?
If you build a file storage system using standard OS file APIs (like writing directly to `ext4` or `NTFS` folders for every user upload), your system will crash under heavy load. Standard filesystems choke on millions of files due to random disk I/O and directory locking. 

Mastering **Log-Structured storage engines** and **CDN cache coherency** is how you build systems that scale to exabytes of data with sub-millisecond lookups.

---

## 2. 🛠️ How it Works (Step-by-Step)

Let's look at the lifecycle of a write and read operation on an individual storage node using a **Bitcask-style (Log-Structured Hash Table)** engine, followed by how we update our CDN edge caches.

### The Lifecycle of a File Write & Edge Invalidation

```
[ Client ] 
    │
    │ 1. PUT /bucket/photo.jpg
    ▼
[ Storage Node ] ──────────┐ (2. Append file data to Active Log)
    │                      ▼
    │               ┌──────────────┐
    │               │  data_01.log │ ◄── [New binary data written at Offset 1024]
    │               └──────────────┘
    │                      │
    │                      ▼ (3. Update In-Memory Index)
    │               ┌──────────────────────────────┐
    │               │ Key: "photo.jpg"             │
    │               │ Val: {File: "data_01.log",   │
    │               │       Offset: 1024,          │
    │               │       Size: 45000}           │
    │               └──────────────────────────────┘
    │
    │ 4. Fire Cache Invalidation Event
    ▼
[ Message Queue (Kafka/SNS) ]
    │
    ▼ 5. Propagate Purge Command
[ CDN Edge Server (PoP) ] ──► [ Drops "photo.jpg" from local SSD Cache ]
```

### Step-by-Step Execution
1. **Append-Only Write**: The Storage Node receives the file. Instead of looking for an empty slot or overwriting an existing sector, it appends the file data sequentially to the end of the current **Active Log File**. This turns slow random writes into blazing-fast sequential writes.
2. **In-Memory Map Update**: The node updates an in-memory hash table (often called a **KeyDir**). It stores the file key mapped to a small metadata struct: `{file_id, offset, file_size}`.
3. **Point Lookup**: When a read request arrives, the node looks up the key in its memory map in $O(1)$ time, performs a single disk `seek` to the exact offset, and streams the bytes out.
4. **CDN Coherency Trigger**: When an update or delete occurs, a ledger entry (or "tombstone" for deletes) is appended. The storage engine fires an asynchronous event to the CDN controller to invalidate that specific cache key globally.

### High-Performance Storage Node Code (Python Simulation)

Here is a highly commented, functional implementation of a Bitcask-style storage node engine. It demonstrates how to perform high-speed append-only writes, in-memory indexing, and single-seek reads.

```python
import os
import struct
import time
from typing import Dict, Tuple

class StorageNodeEngine:
    """
    A high-performance, append-only storage engine simulation 
    resembling Bitcask (the foundation of modern distributed storage nodes).
    """
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        self.active_file_path = os.path.join(data_dir, "node_active.log")
        self.active_file = open(self.active_file_path, "a+b")
        
        # In-Memory Index (KeyDir): maps key -> (file_path, offset, size)
        # This must fit entirely in RAM for O(1) reads.
        self.key_dir: Dict[str, Tuple[str, int, int]] = {}
        self._rebuild_index()

    def put(self, key: str, value: bytes) -> bool:
        """
        Writes data sequentially to the end of the log (Append-Only).
        No random seeks on write!
        """
        key_bytes = key.encode('utf-8')
        key_len = len(key_bytes)
        val_len = len(value)
        timestamp = int(time.time())

        # Move pointer to the end of the active file to guarantee sequential append
        self.active_file.seek(0, os.SEEK_END)
        offset = self.active_file.tell()

        # Binary Header Format: Timestamp (8B) + Key Len (4B) + Value Len (4B)
        header = struct.pack("!QII", timestamp, key_len, val_len)
        
        # Write Header + Key + Value as a single contiguous block
        self.active_file.write(header + key_bytes + value)
        self.active_file.flush() # Ensure OS commits write to disk platter/SSD

        # Calculate the exact start offset of the actual value payload
        value_offset = offset + struct.calcsize("!QII") + key_len
        
        # Update our fast in-memory index
        self.key_dir[key] = (self.active_file_path, value_offset, val_len)
        return True

    def get(self, key: str) -> bytes:
        """
        Retrieves data using 1 fast in-memory hash lookup and 1 disk seek.
        """
        if key not in self.key_dir:
            raise KeyError(f"Key '{key}' not found.")

        file_path, offset, val_len = self.key_dir[key]
        
        # Read from disk using a dedicated read-only file handle to avoid thread contention
        with open(file_path, "rb") as f:
            f.seek(offset)
            return f.read(val_len)

    def _rebuild_index(self):
        """
        On startup, we scan the log sequentially once to rebuild the key_dir in RAM.
        """
        self.active_file.seek(0)
        header_size = struct.calcsize("!QII")
        
        while True:
            header_bytes = self.active_file.read(header_size)
            if not header_bytes or len(header_bytes) < header_size:
                break # Reached end of log
            
            timestamp, key_len, val_len = struct.unpack("!QII", header_bytes)
            key = self.active_file.read(key_len).decode('utf-8')
            
            # Record offset of the value payload
            offset = self.active_file.tell()
            self.key_dir[key] = (self.active_file_path, offset, val_len)
            
            # Skip past value payload to read the next record header
            self.active_file.seek(val_len, os.SEEK_CUR)

# --- Verification Simulation ---
if __name__ == "__main__":
    engine = StorageNodeEngine("./mock_s3_node")
    
    # 1. Store files
    engine.put("user_101/avatar.png", b"IMAGE_BINARY_DATA_A")
    engine.put("user_202/doc.pdf", b"PDF_BINARY_DATA_B")
    
    # 2. Overwrite file (Appends new version to the log, updates RAM index)
    engine.put("user_101/avatar.png", b"NEW_IMAGE_BINARY_DATA_C")
    
    # 3. Retrieve files
    # This reads the NEW version instantly because the in-memory index was redirected!
    print("Retrieved:", engine.get("user_101/avatar.png").decode()) 
    print("Retrieved:", engine.get("user_202/doc.pdf").decode())
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

To stand out as a senior engineer, you must understand the deep system bottlenecks, physical hardware characteristics, and the algorithmic trade-offs of storage engines and edge delivery layers.

### Storage Node Engine Selection: LSM-Tree vs. Bitcask

| Metric | Bitcask (Hash-Table based) | LSM-Tree (Log-Structured Merge-Tree) |
| :--- | :--- | :--- |
| **Write Performance** | **High** (Pure append-only, sequential) | **Medium-High** (Writes to MemTable, flushed to SSTables) |
| **Read Performance** | **Ultra-Fast $O(1)$** (1 direct seek) | **Slower $O(\log N)$** (Must check bloom filters, MemTable, SSTables) |
| **Memory Consumption**| **Very High** (Every key *must* reside in RAM) | **Low** (Only sparse indexes and Bloom filters in RAM) |
| **Range Queries** | **Not Supported** (Hash tables are unordered) | **Excellent** (SSTables are sorted keys) |
| **Best Used For** | S3 metadata servers, photo-hosting backends. | Time-series databases, massive key-value stores. |

#### Storage Node Compaction (Garbage Collection)
Because the write log is append-only, old versions of files (like our old `avatar.png` in the code example) still consume physical disk space. 
* **How it's resolved:** The storage node runs a background **Compaction Process**. It reads old data log files, discards dead keys (files that have been updated or deleted), writes only the active, latest keys into a new compressed log file, and updates the `key_dir` references.

---

### CDN Cache Coherency: Active Invalidation vs. Passive TTL

When an object is modified on S3, keeping the CDN Edge cache in sync is a distributed systems consistency problem. You have two primary strategies:

```
──────────────────────────────────────────────────────────────────────────
Strategy 1: Passive Expiry (TTL)
Client ──► Edge Cache (Stale Data!) ──► Origin (Edge waits for TTL to hit 0)

Strategy 2: Active Purge (Banning)
Origin ──► Push Invalidation Event ──► Edge Node drops cache key instantly
──────────────────────────────────────────────────────────────────────────
```

#### 1. Passive Expiry (TTL)
* **Mechanics**: The storage origin serves files with `Cache-Control: public, max-age=86400` headers. Edge nodes cache this file for 24 hours.
* **Trade-off**: High latency tolerance for updates. If a user updates their profile picture, other users might see the old picture for up to a day.

#### 2. Active Purge (Instant Cache Invalidation)
* **Mechanics**: When a file is updated on the storage node, it emits an event via a message broker (e.g., Apache Kafka) to the CDN control plane. The control plane calls an API on all edge nodes to purge that key: `PURGE /user_101/avatar.png`.
* **The "Thundering Herd" Vulnerability**: If you invalidate a highly popular cached object (e.g., a viral video file), millions of concurrent edge requests will suddenly miss the cache simultaneously and hit the storage origin at once, knocking it offline.
* **Mitigation**: Implement **Request Coalescing** (or "Cache Collapsing") at the CDN edge. If 1,000 requests miss the cache for `video.mp4`, the edge node blocks 999 requests and forwards only *one* request to the storage origin. Once that request resolves, it populates the cache and unblocks the remaining 999 requests.

---

### Interviewer Probe Questions (And How to Answer Them)

#### Probe 1: "If our storage engine's memory-map (KeyDir) is kept entirely in RAM, what happens if the storage node experiences a sudden power failure? Is our index lost forever?"
* **Answer**: No. We can rebuild the entire `key_dir` from scratch by scanning the append-only data log files sequentially from beginning to end on startup. However, if a data log is several terabytes, this scan can take a long time. 
* **Optimization (Hint Files)**: To speed up crash recovery, the storage node periodically writes a **Hint File** to disk during the background compaction process. The hint file is simply a serialized snapshot of the `key_dir` index at that point in time. On startup, the node loads the hint file instantly and only needs to scan the data log from the point where the hint file was created.

#### Probe 2: "How do we prevent disk fragmentation when millions of small files are uploaded and deleted concurrently?"
* **Answer**: Traditional file systems allocate blocks dynamically, leading to fragmentation when files are constantly deleted and modified. Because our storage node engine uses a **Log-Structured** design, all physical writes are contiguous and sequential. We completely bypass disk-level fragmentation. The only "fragmentation" we experience is logical (stale data in older files), which is cleaned up cleanly during background compaction by writing contiguous chunks to new files and deleting old ones.

#### Probe 3: "How does the CDN handle versioning natively without triggering expensive global purge actions every time a file is modified?"
* **Answer**: The industry best practice is **Cache-Busting via Content Hash Versioning**. Instead of saving a file as `/images/logo.png` and invalidating it, we compute the SHA-256 hash of the content and save it as `/images/logo.a8f9c2d1.png`. 
  * Because the filename changes with every edit, the CDN treats it as an entirely new resource.
  * This allows us to set the cache TTL to `infinity` (using `Cache-Control: public, max-age=31536000, immutable`), completely avoiding cache invalidation overhead and origin server stress.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Append-only log-structured engines** (like Bitcask or LSM-Trees) are the industry standard for high-throughput storage nodes because they convert slow, random write operations into highly efficient sequential writes.
2. **In-Memory Indexes** are required to maintain $O(1)$ read performance. If you have to scan the disk to locate a file's physical start position, your system cannot scale.
3. **Active Cache Invalidation** ensures data consistency globally, but it must be paired with **Request Coalescing** at the edge to prevent "Thundering Herd" failures on your storage origin during high-traffic updates.

### 1 Golden Rule
> **"Turn random physical disk writes into sequential log appends, and handle the mess later in the background."**