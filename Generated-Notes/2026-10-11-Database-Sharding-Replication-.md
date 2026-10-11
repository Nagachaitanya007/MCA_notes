---
title: Write-Ahead Log (WAL) Streaming: LSNs, Engine Internals, and Replication Pipelines
date: 2026-10-11T10:31:42.821175
---

# Write-Ahead Log (WAL) Streaming: LSNs, Engine Internals, and Replication Pipelines

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
When a primary database changes, it doesn't replicate data by copying entire tables or re-running complex SQL queries on replicas. Instead, it streams an append-only binary journal of the exact, low-level byte alterations made to its storage pages. This journal is the **Write-Ahead Log (WAL)** (known as the *redo log* in Oracle or the *binary log/binlog* in MySQL when running logical replication). Replicas continuously ingest this stream and apply the exact same byte changes to their own local storage files.

#### The Courtroom Stenographer Analogy
Imagine a busy courtroom. 
* **The Bad Approach:** Every time the Judge delivers a verdict, three junior lawyers run outside and attempt to re-enact the entire trial from memory to update their records. They will inevitably miss nuances, arrive at slightly different interpretations, and waste massive amounts of time.
* **The WAL Streaming Approach:** A certified stenographer sits next to the judge, recording every single syllable in chronological order with precise line numbers (**Log Sequence Numbers / LSN**). Assistants do not observe the trial; they simply sit in backrooms connected to a high-speed teletype that feeds them the stenographer’s raw transcript line by line. They copy the exact words onto their duplicate books. If an assistant disconnects, they just request: *"Send me everything after Line 4,120."*

```
[Transaction] ──> [Stenographer (WAL with LSN)] ──> [Teletype (Network)] ──> [Copyists (Replicas)]
```

#### Why should I care? What problem does it solve today?
* **Zero Query Execution Overhead:** Replicas do not parse SQL, evaluate query plans, resolve join algorithms, or fire triggers. They just apply pre-calculated page diffs.
* **Byte-for-Byte Determinism:** It eliminates non-deterministic bugs (e.g., executing `NOW()`, `RAND()`, or `UUID()` on a replica yielding a different value than on the primary).
* **Fault-Tolerant Reconnection:** If network connectivity drops between data centers, the replica simply tells the primary its last processed byte offset to resume instantly without full-database re-syncs.

---

### 2. 🛠️ How it Works (Step-by-Step)

```
PRIMARY ENGINE                                                  REPLICA ENGINE
+------------------------------------+                         +------------------------------------+
| 1. Client TX executes              |                         |                                    |
| 2. Changes written to WAL Buffer   |                         |                                    |
| 3. Buffer flushed to Disk (fsync)  |                         |                                    |
| 4. Primary LSN updated             |                         |                                    |
|         │                          |                         |                                    |
|         ▼                          |                         |                                    |
|  [ WAL Sender ] ──(TCP Stream)─────┼────────────────────────>│  [ WAL Receiver ]                  |
+------------------------------------+                         |          │                         |
                                                               |          ▼                         |
                                                               |  5. Written to Relay Log / WAL     |
                                                               |  6. Flushed to Disk                |
                                                               |  7. Startup / Apply Worker         |
                                                               |     modifies shared buffer pool    |
                                                               |  8. Send ACK (LSN) to Primary      |
                                                               +------------------------------------+
```

#### Step-by-Step Execution:
1. **Log Before Data (Write-Ahead):** Before modifying any in-memory page in the primary's `Shared Buffer Pool`, a record describing the change is written to an in-memory `WAL Buffer`.
2. **Atomic Disk Flush:** At transaction commit, the WAL buffer is flushed to non-volatile disk (`fsync`). The record is stamped with a monotonically increasing 64-bit integer called a **Log Sequence Number (LSN)**, representing its exact byte offset in the write log.
3. **Log Shipping Over TCP:** A dedicated background process (e.g., PostgreSQL’s `walsender`) continuously monitors the local WAL. As new bytes hit the log, it pushes them over a persistent socket to the replica.
4. **Ingestion & Buffering:** On the replica, a `walreceiver` thread reads raw bytes from the network socket, writes them to local storage (sometimes referred to as a *Relay Log*), and tracks the maximum flushed LSN.
5. **State Machine Replay:** A background recovery process (`Startup/Apply Worker`) reads incoming WAL records in strict sequence and updates the replica's local buffer cache and tables on disk.
6. **Progress Feedback (ACK):** The replica periodically writes back a small acknowledgement payload informing the primary: *"I have flushed up to LSN `0/3F0012A` and applied up to LSN `0/3F00100`."*

#### Simulating the WAL Streaming Protocol

Below is a clean, dependency-free Python implementation of a Primary WAL Sender and Replica WAL Receiver streaming byte records tracked by an integer Log Sequence Number (LSN).

```python
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class WALRecord:
    lsn: int           # Monotonically increasing byte offset
    tx_id: int         # Transaction ID
    page_id: int       # Target disk block/page
    payload: bytes     # Low-level page differential

class MockPrimaryWAL:
    def __init__(self):
        self.wal_log: list[WALRecord] = []
        self.current_lsn: int = 0

    def commit_transaction(self, tx_id: int, page_id: int, payload: bytes) -> WALRecord:
        """Appends a change to the primary WAL and advances the LSN."""
        record_size = len(payload) + 16  # Payload + metadata overhead
        self.current_lsn += record_size
        record = WALRecord(lsn=self.current_lsn, tx_id=tx_id, page_id=page_id, payload=payload)
        self.wal_log.append(record)
        return record

    def stream_from(self, last_received_lsn: int):
        """Yields all WAL records created after the replica's last known LSN."""
        for record in self.wal_log:
            if record.lsn > last_received_lsn:
                yield record

class MockReplicaEngine:
    def __init__(self, name: str):
        self.name = name
        self.last_applied_lsn = 0
        self.storage_pages: dict[int, bytes] = {}

    def ingest_and_apply(self, wal_stream) -> int:
        """Receives streaming WAL records and updates local engine state."""
        records_applied = 0
        for record in wal_stream:
            # Enforce strict ordering to prevent split-state divergence
            if record.lsn <= self.last_applied_lsn:
                continue

            # Apply page diff directly to storage (no SQL parsing needed)
            self.storage_pages[record.page_id] = record.payload
            self.last_applied_lsn = record.lsn
            records_applied += 1
            print(f"[{self.name}] Applied TX {record.tx_id} -> Page {record.page_id} at LSN {record.lsn}")
            
        return records_applied

# --- Execution Example ---
if __name__ == "__main__":
    primary = MockPrimaryWAL()
    replica = MockReplicaEngine("Replica-01")

    # 1. Primary writes 2 transactions
    primary.commit_transaction(tx_id=101, page_id=42, payload=b"UPDATE user SET name='Alice'")
    primary.commit_transaction(tx_id=102, page_id=43, payload=b"INSERT INTO orders (id) VALUES (1)")

    # 2. Replica catches up
    stream = primary.stream_from(last_received_lsn=replica.last_applied_lsn)
    replica.ingest_and_apply(stream)

    # 3. Primary commits another transaction; Replica catches up incrementally
    primary.commit_transaction(tx_id=103, page_id=42, payload=b"UPDATE user SET name='Bob'")
    stream = primary.stream_from(last_received_lsn=replica.last_applied_lsn)
    replica.ingest_and_apply(stream)
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Internal Magic: Physical vs. Logical WAL
* **Physical WAL Replication (PostgreSQL default):** Records literal binary changes to disk pages (e.g., *"In file 16384, block 92, at byte offset 40, replace bytes `0xAA` with `0xFF`"*). Replicas must run the exact same operating system architecture, major database version, and byte-endianness.
* **Logical WAL Replication:** The engine parses the physical log into logical event streams (e.g., *"Insert row into table `orders` with values `(...)`"* via decode plugins). This allows cross-version streaming (e.g., Postgres 14 to Postgres 16) and partial-database streaming, but adds heavy CPU deserialization cost on the primary.

#### Group Commit & Disk Latency Amortization
Calling `fsync()` on spinning rust or NVMe drives for every individual transaction commits kills throughput (capping out at around 1,000–5,000 TPS due to physical hardware storage limits).
Modern database kernels implement **Group Commit**:
1. Transaction A issues a `COMMIT` and is put to sleep waiting on an OS condition variable.
2. The engine deliberately waits a micro-fraction of a millisecond (`wal_writer_delay` / `binlog_group_commit_sync_delay`).
3. Transactions B, C, and D arrive in that microsecond window and append their logs to the same shared memory buffer.
4. A single leader thread calls `fsync()` once for all four transactions, flushes the entire block, and wakes up all four worker threads simultaneously.

```
TX 1 Commits ──┐
TX 2 Commits ──┼──> [WAL Memory Buffer] ──(Single fsync)──> [Disk & Network Stream]
TX 3 Commits ──┘
```

#### Trade-offs of Physical WAL Streaming

| Dimension | Physical WAL Streaming | Logical Log Shipping / Statements |
| :--- | :--- | :--- |
| **CPU Overhead** | Extremely low (straight binary page copies). | Moderate-to-High (deserializes and serializes row tuples). |
| **Engine Coupling** | Identical CPU architecture & DB version required. | Heterogeneous DB versions, platforms, and schemas. |
| **Partial Replication** | Impossible (Entire DB cluster must be replicated). | Easy (Can replicate a single table or subset of columns). |
| **Replica Workload** | Read-only strictly (Replica cannot run local DDL/writes). | Permissive (Replica can have local indexes, triggers, or tables). |

---

#### 🎯 Interviewer Probes (Tricky Questions & How to Answer)

##### Probe 1: *"What happens if a replica disconnects for two hours, and the primary runs out of disk space? How do Replication Slots protect or hurt you?"*
* **The Trap:** Thinking replication slots are a magic bullet with no downside.
* **The Senior Answer:** A **Replication Slot** instructs the primary's WAL recycler: *"Do not delete or overwrite any WAL files on disk past LSN `X` because Replica-1 hasn't confirmed receipt yet."* If the replica drops for 2 hours during high write traffic, the primary will retain every single WAL segment. If `max_slot_wal_keep_size` is not configured, **the primary's disk will hit 100% capacity, freezing the entire production system**. Production setups must enforce maximum slot thresholds or fallback to WAL archive storage (e.g., streaming WAL segments to Amazon S3 via tools like `pgBackRest` or `wal-g`).

##### Probe 2: *"Why can a long-running read query on a read-replica cause replication lag or fail with a 'canceling statement due to conflict with recovery' error?"*
* **The Trap:** Assuming reads on a replica have zero interaction with the incoming WAL stream.
* **The Senior Answer:** The primary can run a `VACUUM` process that removes dead row versions (garbage-collected dead tuples) and logs that removal to the physical WAL. When the replica replays that WAL record, it attempts to physically excise those data blocks. However, if an active, long-running `SELECT` query on the replica is currently reading those exact tuples under Multi-Version Concurrency Control (MVCC), an explicit conflict occurs. The replica must either:
  1. Pause replaying the WAL, causing the replica's **replication lag to climb rapidly**, or
  2. Kill the long-running query after `max_standby_streaming_delay` is exceeded, raising a query cancellation error to the client.

##### Probe 3: *"How does the WAL engine distinguish between a committed and an uncommitted transaction in the event of a sudden crash during streaming?"*
* **The Trap:** Thinking the database only writes to the WAL when a transaction is successful.
* **The Senior Answer:** In high-volume systems, transactions spanning multiple gigabytes of data write to the WAL *continuously* before they commit to avoid overflowing the in-memory buffer pool. The log contains explicit lifecycle markers: `BEGIN`, intermediate operational records, and a terminating `COMMIT` (or `ABORT`) record. During recovery, the replica or restarted instance executes an **ARIES-style recovery algorithm**: it performs a *Redo pass* scanning forward from a checkpoint, followed by an *Undo pass* scanning backward to roll back any transactions whose LSN changes were applied to pages but lack a final `COMMIT` record.

---

### 4. ✅ Summary Cheat Sheet

* **3 Key Takeaways:**
  1. **WAL is the Real Database; Tables are Just Materialized Views:** Disk pages are volatile, cached structures; the append-only write-ahead log is the true, sequential record of state and ground truth.
  2. **LSN is the Global Clock:** Replication coordination does not rely on wall-clock timestamps (which suffer from NTP drift). It depends strictly on the integer byte offsets represented by Log Sequence Numbers.
  3. **Replay is Cheap, Synchronization is Not:** Physical streaming requires almost zero CPU on the replica compared to SQL re-execution, but requires tight coupling between primary and standby architectures.

* **1 "Golden Rule" to Remember:**
  > *"Never monitor replication health using elapsed time alone; monitor byte lag via `pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)`. Time is subjective; byte distance is absolute."*