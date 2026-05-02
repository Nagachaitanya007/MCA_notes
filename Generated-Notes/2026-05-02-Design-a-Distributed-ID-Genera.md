---
title: Design a Distributed ID Generator (Snowflake ID)
date: 2026-05-02T10:31:24.427179
---

# Design a Distributed ID Generator (Snowflake ID)

1. 💡 **The "Big Picture" (Plain English)**
   - **What is it?** It's a way to generate billions of unique numbers (IDs) across many different servers simultaneously without them ever needing to talk to each other to "check" if a number is taken.
   - **Real-World Analogy:** Imagine a global car manufacturer like Toyota. They have factories in Japan, the USA, and Germany. To ensure every car has a unique VIN (Vehicle Identification Number), they don't want every factory calling a central office in Tokyo every time a car rolls off the line—that would cause a massive traffic jam of phone calls. Instead, they give each factory a unique "Factory ID." Each car's VIN is then: `[Date] + [Factory ID] + [Car Number of the Day]`. This guarantees no two cars will ever have the same ID, even if they are built at the exact same second on different continents.
   - **Why care?** In modern apps (like Twitter or Instagram), you can't rely on a single database to hand out IDs (like `1, 2, 3...`) because that database would eventually crash under the pressure of millions of users. You need a system that is **decentralized, fast, and generates IDs that are roughly in chronological order.**

2. 🛠️ **How it Works (Step-by-Step)**
   The Snowflake ID is a **64-bit integer** (fits into a standard `long` in most languages). We divide those 64 bits into specific "zones":

   1. **Sign Bit (1 bit):** Always `0`. This keeps the number positive.
   2. **Timestamp (41 bits):** Current time in milliseconds (relative to a custom "epoch" or start date). This gives us about 69 years of IDs.
   3. **Machine/Worker ID (10 bits):** A unique ID assigned to the specific server (up to 1,024 servers).
   4. **Sequence Number (12 bits):** A counter for IDs generated on the *same* server within the *same* millisecond. It resets to 0 every millisecond.

   ### The Flow (ASCII Art)
   ```text
   0 | 0000000000 0000000000 0000000000 0000000000 0 | 0000000000 | 000000000000
   ↑   ↑                                               ↑            ↑
   Unused   Timestamp (41 bits)                   Worker ID    Sequence (12 bits)
   ```

   ### Code Snippet (Simplified Logic)
   ```java
   public synchronized long nextId() {
       long timestamp = System.currentTimeMillis();

       // If we are in the same millisecond as the last ID, increment the sequence
       if (lastTimestamp == timestamp) {
           sequence = (sequence + 1) & 4095; // 12 bits max
           if (sequence == 0) {
               // Sequence exhausted! Wait for the next millisecond
               timestamp = waitNextMillis(lastTimestamp);
           }
       } else {
           sequence = 0; // New millisecond, reset counter
       }

       lastTimestamp = timestamp;

       // Use Bit Shifting to pack everything into one 64-bit Long
       return ((timestamp - EPOCH) << 22) | (workerId << 12) | sequence;
   }
   ```

3. 🧠 **The "Deep Dive" (For the Interview)**
   - **Bit Manipulation vs. String Concatenation:** We use bitwise operators (`<<` and `|`) because they are computationally "free." Modern CPUs process these in a single cycle. Storing IDs as 64-bit integers instead of UUID strings saves massive amounts of space in database indexes (8 bytes vs. 36 bytes).
   - **K-Sortable IDs:** Because the timestamp is the most significant part (the first bits), Snowflake IDs are "roughly" sorted by time. This is a massive win for Databases (B-Trees) because new IDs are inserted at the end of the index rather than randomly in the middle, reducing "page splits" and disk I/O.
   - **The Trade-off: Clock Drift:** This is the "Achilles heel." Snowflake relies on the system clock. If a server's clock is synchronized backwards (via NTP), it could generate a timestamp it already used, leading to duplicate IDs.
     - *Solution:* If the code detects `currentTimestamp < lastTimestamp`, it must throw an error or wait for the clock to catch up.
   - **Interviewer Probe: "How do you assign the Worker ID?"**
     - *Answer:* You shouldn't hardcode them. Usually, you use a coordination service like **Zookeeper** or **Etcd**. When a new microservice starts up, it registers itself, and the coordinator gives it the next available ID from 0 to 1023.
   - **Interviewer Probe: "What if you need more than 4,096 IDs per millisecond?"**
     - *Answer:* You can adjust the bit allocation. You could take bits from the Worker ID and give them to the Sequence, but 4 million IDs per second per server is usually overkill for most companies.

4. ✅ **Summary Cheat Sheet**
   - **High Availability:** No central "ID issuer" means no single point of failure.
   - **Performance:** Generates IDs in memory (~10,000+ per ms) without network calls.
   - **Sortable:** Naturally sorts by time, which makes databases happy.
   - **The Golden Rule:** **Timestamp first, then Machine, then Counter.** This specific order ensures your IDs are chronological and unique across the entire world.