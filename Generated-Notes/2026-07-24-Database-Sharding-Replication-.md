---
title: Local vs. Global Secondary Indexes in Sharded Databases
date: 2026-07-24T10:32:02.968574
---

# Local vs. Global Secondary Indexes in Sharded Databases

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
When you shard a database, you break a massive table into smaller pieces distributed across multiple servers using a **Shard Key** (like `user_id`). Finding data by `user_id` is lightning fast because the router knows exactly which server holds that user. 

But what happens when a user tries to log in using their `email` instead of `user_id`? The system has no idea which server holds that email address! To solve this, you need a **Secondary Index** strategy:
*   **Local Secondary Index (LSI):** Every individual shard maintains its own index for the data stored on that specific machine.
*   **Global Secondary Index (GSI):** A completely separate, centralized (or independently sharded) index table mapped across the whole cluster that tracks where every record lives.

#### Real-World Analogy
Imagine a massive university library spread across 5 different buildings, organized by **Student ID** (the Primary Shard Key).
*   **Local Index Strategy:** Every building has its own small catalog desktop listing books by **Title** (Secondary Attribute), but *only* for books physically located inside that specific building. If you search for "Hamlet", you have to call all 5 buildings and ask each one if they have it.
*   **Global Index Strategy:** The main university entrance has one central master catalog by **Title**. You look up "Hamlet", and the card tells you: *"Go directly to Building 3, Shelf 4."*

#### Why should I care?
If you pick the wrong index strategy, a simple query like `SELECT * FROM users WHERE email = 'alex@dev.com'` will trigger a **Scatter-Gather query**—forcing your application to ping dozens or hundreds of database servers simultaneously just to fetch a single row. This causes latency spikes, connection pool exhaustion, and completely destroys the performance benefits of sharding.

---

### 2. 🛠️ How it Works (Step-by-Step)

#### Local Secondary Indexing (Scatter-Gather Flow)
1. **Write:** Data is written to Shard A based on `user_id`. Shard A updates its own local `email` index within the same local transaction.
2. **Read (by non-shard key):** Query router receives `WHERE email = 'alex@dev.com'`.
3. **Scatter:** Router sends the exact same query parallelly to *all* $N$ shards.
4. **Gather:** Every shard checks its local index. Shards with no match return empty; Shard A returns the record.
5. **Aggregate:** The router combines the responses and returns the result to the client.

#### Global Secondary Indexing (Direct Lookup Flow)
1. **Write:** Data is written to Shard A (sharded by `user_id`). An update is also dispatched (synchronously or asynchronously) to the **Global Index Server** (sharded by `email`).
2. **Read (by non-shard key):** Query router receives `WHERE email = 'alex@dev.com'`.
3. **Index Lookup:** Router queries the Global Index table (sharded by `email`) to get the primary key / shard location (`user_id = 1042`, `Shard A`).
4. **Data Fetch:** Router queries Shard A directly to fetch the complete user payload.

#### Mermaid Diagram: Query Execution Flow

```mermaid
graph TD
    subgraph Local Index Strategy (Scatter-Gather)
        Client1[Client Query: email='a@b.com'] --> Router1[Query Router]
        Router1 -->|Parallel Request| S1[Shard 1 - Local Index]
        Router1 -->|Parallel Request| S2[Shard 2 - Local Index]
        Router1 -->|Parallel Request| S3[Shard 3 - Local Index]
        S1 -. No Match .-> Router1
        S2 -->|Match Found!| Router1
        S3 -. No Match .-> Router1
    end

    subgraph Global Index Strategy (Two-Step Lookup)
        Client2[Client Query: email='a@b.com'] --> Router2[Query Router]
        Router2 -->|1. Lookup Shard Location| GSI[Global Index Shard: email]
        GSI -->|2. Returns: Shard 2, ID 1042| Router2
        Router2 -->|3. Direct Point Query| S2_G[Shard 2 - Data]
    end
```

#### Code Snippet: Scatter-Gather Query Coordinator (Node.js/TypeScript)

Here is a simplified example showing how a query router executes a parallel Scatter-Gather operation over local indexes, including timeout handling and aggregation:

```typescript
import { Pool } from 'pg';

interface ShardConnection {
  id: string;
  pool: Pool;
}

class ShardQueryRouter {
  private shards: ShardConnection[];

  constructor(shards: ShardConnection[]) {
    this.shards = shards;
  }

  /**
   * Executes a Scatter-Gather search across all shards for a non-shard key.
   */
  async findUserByEmail(email: string, timeoutMs: number = 2000): Promise<any | null> {
    const query = 'SELECT id, user_id, email, name FROM users WHERE email = $1 LIMIT 1';
    
    // 1. SCATTER: Fire queries to all shards in parallel with a hard timeout
    const queryPromises = this.shards.map(async (shard) => {
      const client = await shard.pool.connect();
      try {
        // Enforce a strict statement timeout per shard to prevent tail-latency bloat
        await client.query(`SET statement_timeout = ${timeoutMs}`);
        const res = await client.query(query, [email]);
        return res.rows[0] || null;
      } catch (err) {
        console.error(`Error querying shard ${shard.id}:`, err);
        return null; // Fail open / treat error as no match for simplicity
      } finally {
        client.release();
      }
    });

    // 2. GATHER: Wait for all parallel queries to resolve
    const results = await Promise.all(queryPromises);

    // 3. AGGREGATE: Extract the first non-null result across all shard responses
    const matchedUser = results.find((user) => user !== null);

    return matchedUser || null;
  }
}
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Internal Trade-Off Matrix

| Metric | Local Secondary Index (LSI) | Global Secondary Index (GSI) |
| :--- | :--- | :--- |
| **Write Performance** | **Ultra-Fast / Atomically Consistent**: Local transaction updates both data and index in one ACID operation. | **Slower / Complex**: Requires distributed write (2PC) or asynchronous event streams (CDC/Outbox Pattern). |
| **Read Latency** | **Poor ($O(N)$ Shards)**: Scalability degrades as cluster grows due to fan-out overhead. | **High & Predictable ($O(1)$)**: Max 2 network hops regardless of total cluster size. |
| **Blast Radius** | **High**: One slow database node stalls the entire scatter-gather response. | **Low**: Reads only touch the index partition and the specific data shard. |
| **Storage Overhead** | **Low**: Indexes live alongside data; easily partitioned cleanly. | **High**: Requires duplicate tables partitioned by different keys plus metadata pointers. |

#### Advanced Engine Internals & Tail Latency Explosions
In a **Scatter-Gather (Local Index)** architecture, system latency is dictated by the **slowest node**, not the average. If a single shard suffers a GC pause, disk I/O spike, or lock contention, the entire client request waits.

Mathematically, if $p$ is the probability of a single server being slow ($p = 0.01$, or 99th percentile latency), and you scatter a query across $N = 100$ shards, the probability $P_{slow}$ that the overall request is slow is:
$$P_{slow} = 1 - (1 - p)^N = 1 - (0.99)^{100} \approx 63.4\%$$
*A query scattered across 100 shards will experience a tail-latency spike over 63% of the time!*

To solve this for **Global Secondary Indexes (GSI)** without sacrificing write availability, systems like **Amazon DynamoDB** or **Cassandra** decouple the index write using **Asynchronous Logical Replication**:
1. Primary write hits Primary Shard $S_P$ -> append to Storage Engine WAL (Write-Ahead Log).
2. background thread or engine-level CDC (Change Data Capture) pipeline reads WAL.
3. Log record is asynchronously dispatched to Index Shard $S_I$.
4. **Trade-off:** Reads on GSIs are **eventually consistent**. A client writing a new record and immediately querying via the GSI may encounter a transient stale read (phantom read anomaly).

---

#### 💡 Interviewer Probe Questions & Senior Responses

##### Q1: "How would you implement offset pagination (e.g., `LIMIT 10 OFFSET 1000`) on a non-shard key using Local Secondary Indexes?"
*   **Junior Answer:** "I'll just pass `LIMIT 10 OFFSET 1000` to all shards and sum the results."
*   **Senior Answer:** "Passing the offset to all shards yields incorrect data. To return offset $K$ with limit $L$, the coordinator must request `LIMIT (K + L)` from **every single shard**, pull all $(K + L) \times N$ records over the network into memory, sort them globally on the router, and then slice the target range. This causes massive memory bloat and $O(N \cdot (K+L))$ bandwidth explosion. To prevent this, we must enforce **Cursor-Based (Keyset) Pagination** (e.g., `WHERE (created_at, id) > (:last_seen_time, :last_seen_id) LIMIT 10`) combined with a bounded priority queue on the coordinator."

##### Q2: "If we choose a Global Secondary Index, how do we guarantee unique constraints (e.g., `UNIQUE(email)`) across a sharded database?"
*   **Senior Answer:** "Enforcing uniqueness across shards natively requires distributed locking or Two-Phase Commit (2PC), which kills write throughput. There are two standard production patterns to bypass this:
    1. **Shard by the Unique Field:** Make `email` the Primary Shard Key, and store `user_id` as an attribute inside that shard.
    2. **Deterministic Hash Claim Strategy (Redis/DynamoDB):** Before writing to the database, issue an atomic `SETNX` (Set If Not Exists) against a dedicated fast key-value store using the normalized `email` as the lock key. Alternatively, write a 'stub record' synchronously to the GSI partition (sharded by `email`) *first*. If the GSI insert succeeds, proceed with the primary write; if it fails due to key collision, roll back."

##### Q3: "What mitigation techniques can you apply if business constraints force you to use Scatter-Gather (LSI) queries?"
*   **Senior Answer:** "If LSI is unavoidable, we mitigate tail latency and resource consumption using three techniques:
    1. **Hedge Requests (Speculative Retries):** Send the query to all shards; if a specific shard doesn't respond within the 95th percentile expected duration, fire a duplicate query to that shard's read-replica.
    2. **Scatter-Gather Fan-out Limits / Workers Pool:** Do not open unbounded connection pools. Use bounded concurrency workers on the coordinator to stream and aggregate responses.
    3. **Two-Tiered Routing Caching:** Cache the resolution map (`email -> user_id`) in an in-memory cache (e.g., Redis). On cache miss, fall back to Scatter-Gather, then populate the cache."

---

### 4. ✅ Summary Cheat Sheet

```
+-----------------------------------------------------------------------+
|                 LOCAL VS. GLOBAL SECONDARY INDEXES                    |
+-----------------------------------------------------------------------+
|   LOCAL INDEX (LSI)                   |   GLOBAL INDEX (GSI)          |
|   - Indexed alongside data shard      |   - Separate index partition  |
|   - Writes: Fast & ACID local         |   - Writes: Async / Dist.     |
|   - Reads: Scatter-Gather (O(N))      |   - Reads: Point Query (O(1)) |
|   - Best for: Low fan-out / write heavy|  - Best for: Read-heavy / SLA |
+-----------------------------------------------------------------------+
```

#### 3 Key Takeaways
1. **Sharding Keys direct queries, Secondary Indexes search queries.** Without a secondary index strategy, non-shard-key queries default to expensive Scatter-Gather operations.
2. **Local Indexes trade Read performance for Write speed.** Writes remain atomic and fast per node, but reads scale poorly as the cluster grows ($O(N)$ shards).
3. **Global Indexes trade Write complexity for Read speed.** Reads require at most 2 targeted hops ($O(1)$), but writes require eventual consistency pipelines or distributed transactions.

#### 1 "Golden Rule"
> **Design your primary shard keys around your highest-frequency write pathways, and build Global Secondary Indexes (GSIs) asynchronously via CDC for your high-SLA read pathways.** Never let a critical, latency-sensitive endpoint execute an unbuffered Scatter-Gather query over local indexes across dozens of shards.