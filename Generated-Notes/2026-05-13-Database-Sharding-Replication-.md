---
title: Data Consistency in Replication: Synchronous vs. Asynchronous Models
date: 2026-05-13T10:31:33.343427
---

# Data Consistency in Replication: Synchronous vs. Asynchronous Models

1. 💡 **The "Big Picture" (Plain English):**
   - **What is this?** Imagine you have a main notebook (Primary Database) and several backup notebooks (Replicas). This subtopic is about *when* we tell the boss the work is done: Do we wait until the backups are written, or do we say "done" the moment the main notebook is updated?
   - **Real-World Analogy:** Imagine ordering a pizza. 
     - **Synchronous:** You stand at the counter and refuse to leave until you see the pizza boxed and handed to the delivery driver. You *know* the delivery is safe, but you're stuck waiting at the store.
     - **Asynchronous:** You pay, the cashier says "We got it!", and you walk out. The pizza might get dropped on the way, but you're already home watching TV.
   - **Why care?** If you choose the wrong one, your app will either be painfully slow (Sync) or users will see "ghost data" where their updates seemingly disappear for a few seconds (Async).

2. 🛠️ **How it Works (Step-by-Step):**

   **The Synchronous Flow:**
   1. The **Client** sends a `write` request to the **Leader**.
   2. The **Leader** writes the data and immediately sends it to the **Follower**.
   3. The **Leader** waits. It does not respond to the client yet.
   4. The **Follower** writes the data and sends an `ACK` (Acknowledgement) back.
   5. The **Leader** finally tells the **Client**: "Success!"

   **The Asynchronous Flow:**
   1. The **Client** sends a `write` request to the **Leader**.
   2. The **Leader** writes the data and immediately tells the **Client**: "Success!"
   3. The **Leader** sends the data to the **Follower** in the background (eventually).

   **Mermaid Diagram (The Flow):**
   ```mermaid
   sequenceDiagram
       participant C as Client
       participant L as Leader (Primary)
       participant F as Follower (Replica)

       Note over C, F: Synchronous Replication
       C->>L: Write Data
       L->>F: Replicate Data
       F-->>L: OK (Ack)
       L-->>C: Success! (Slow but Safe)

       Note over C, F: Asynchronous Replication
       C->>L: Write Data
       L-->>C: Success! (Fast but Risky)
       L->>F: Replicate Data (Background)
   ```

   **Example Config (PostgreSQL Style):**
   ```sql
   -- To make a replica synchronous in Postgres:
   -- In postgresql.conf
   synchronous_commit = on
   synchronous_standby_names = 'replica_1' -- The leader waits for 'replica_1'
   ```

3. 🧠 **The "Deep Dive" (For the Interview):**

   - **The Internals (WAL & Log Shipping):**
     In modern databases (Postgres, MySQL, MongoDB), replication isn't usually sending "SQL commands." Instead, the Leader sends **Write-Ahead Log (WAL)** segments or **Oplog** entries. In *Synchronous* mode, the Leader's "Commit" LSN (Log Sequence Number) cannot advance until the Follower confirms it has flushed that same LSN to its own disk.
   
   - **The Trade-offs (CAP Theorem):**
     - **Synchronous:** Prioritizes **Consistency**. If the Follower crashes or the network blips, the Leader stops accepting writes. Your system goes down (Availability drops) to ensure no data is lost.
     - **Asynchronous:** Prioritizes **Availability** and **Latency**. The Leader keeps working even if Followers are offline. However, if the Leader dies before the background sync happens, you suffer **Data Loss**.

   - **Interviewer Probes:**
     - *Q: "What is 'Semi-Synchronous' replication?"*
       - **Answer:** It's a middle ground. The Leader waits for *at least one* replica to acknowledge, but not all of them. This balances safety and speed.
     - *Q: "How do you solve the 'Read-Your-Own-Writes' problem in Async replication?"*
       - **Answer:** If a user updates their profile (Leader) and immediately refreshes (reading from a lagging Follower), their update "disappears." To fix this, we can route "own-profile" reads to the Leader for a few seconds or use **Version Tracking/Session Consistency**.
     - *Q: "What happens to a Sync setup if the network between nodes has a 100ms spike?"*
       - **Answer:** Every single write request to your database will now take at least 100ms longer. Your application's throughput will collapse.

4. ✅ **Summary Cheat Sheet:**
   - **Synchronous:** High Durability (No data loss), High Latency (Slow), Low Availability (One failure stops the world).
   - **Asynchronous:** Low Latency (Fast), High Availability, Risk of "Lag" and Data Loss during failover.
   - **Semi-Sync:** The "Goldilocks" zone—waits for one ACK then moves on.

   **Golden Rule:**
   > "Choose **Asynchronous** for performance-first apps (social media, logs); choose **Synchronous** only when data loss is more expensive than system downtime (banking, core inventory)."