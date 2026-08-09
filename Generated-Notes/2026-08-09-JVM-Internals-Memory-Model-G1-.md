---
title: JVM Memory Pacing and Allocation Stalls: How G1 and ZGC Prevent Allocation Failures
date: 2026-08-09T04:46:44.350044
---

# JVM Memory Pacing and Allocation Stalls: How G1 and ZGC Prevent Allocation Failures

1. 💡 The "Big Picture" (Plain English):
   - What is this in simple terms?
     When your application creates Java objects faster than the Garbage Collector (GC) can clean them up, the JVM runs out of free space. Instead of crashing immediately or freezing the entire application, modern JVMs use **Memory Pacing** and **Allocation Stalls** to artificially slow down or pause *only* the threads requesting new memory until the GC catches up.
   - Use a real-world analogy:
     Imagine a busy fast-food kitchen. The cooks (Application Threads) make food on paper plates (allocating objects), and a dishwasher (Garbage Collector) cleans and recycles the trays. If the cooks start making food faster than the dishwasher can clean, the kitchen runs out of trays. 
     - **Old JVM strategy:** Freeze the entire kitchen—nobody moves until the dishwasher cleans everything (**Stop-The-World Full GC**).
     - **Modern JVM strategy (G1 / ZGC Pacing):** Tap the fastest cooks on the shoulder and force them to slow down for a few milliseconds (**Allocation Pacing**). If space completely runs out, that specific cook waits at the counter until a clean tray is ready (**Allocation Stall**), while other non-allocating cooks keep working.
   - Why should I care?
     If your application experiences mysterious micro-spikes in response time—even when your GC logs show near-zero pause times—you are likely hitting Memory Pacing or Allocation Stalls. Understanding this helps you diagnose performance bottlenecks under heavy load.

---

2. 🛠️ How it Works (Step-by-Step):

   ### The Allocation Path Flow:
   1. **Fast-Path Allocation:** A thread attempts to allocate an object in its Thread-Local Allocation Buffer (TLAB). If space is available, memory is allocated instantly with zero locking.
   2. **Slow-Path Allocation:** If the TLAB is full, the thread requests space directly from the shared JVM Heap.
   3. **Pacing Threshold Check:** The JVM checks the current GC phase and heap occupancy. If the object creation rate exceeds the GC cleaning rate, **Allocation Pacing** kicks in.
   4. **Micro-Delay Injected:** The JVM forces the allocating thread to sleep or yield for a tiny duration (e.g., 10 microseconds to a few milliseconds) to throttle allocation pressure.
   5. **Allocation Stall (Fallback):** If the collector cannot free memory fast enough and available heap drops to zero, the thread enters an **Allocation Stall**—blocking completely until the GC frees a region/page.

```
+-------------------------------------------------------------------+
|                        Application Thread                         |
+-------------------------------------------------------------------+
                                  |
                                  v
                   +-----------------------------+
                   |  1. Try TLAB Allocation     |
                   +-----------------------------+
                                  |
                        +---------+---------+
                        |                   |
                     (Success)           (Failure)
                        |                   |
                        v                   v
                 +--------------+   +-------------------------------+
                 | Fast Return  |   | 2. Shared Heap Allocation     |
                 +--------------+   +-------------------------------+
                                                    |
                                                    v
                                    +-------------------------------+
                                    | 3. Is Allocation Rate > GC?   |
                                    +-------------------------------+
                                                    |
                                          +---------+---------+
                                          |                   |
                                         (No)               (Yes)
                                          |                   |
                                          v                   v
                                   +--------------+   +-------------------+
                                   | Allocate Mem |   | 4. Inject Pacing  |
                                   +--------------+   |    Micro-Delay    |
                                                      +-------------------+
                                                                |
                                                                v
                                                      +-------------------+
                                                      | Heap Exhausted?   |
                                                      +-------------------+
                                                        |               |
                                                      (No)            (Yes)
                                                        |               |
                                                        v               v
                                                +--------------+  +---------------+
                                                | Allocate Mem |  | 5. ALLOCATION |
                                                +--------------+  |    STALL      |
                                                                  | (Thread Block)|
                                                                  +---------------+
```

### Demonstration Code:

```java
import java.util.ArrayList;
import java.util.List;

/**
 * Demonstrates high object allocation rate leading to GC pressure.
 * Run with ZGC or G1 GC logging enabled to observe pacing and stalls:
 * 
 * -XX:+UseZGC -Xms512m -Xmx512m -Xlog:gc*,gc+pacing=debug
 * OR
 * -XX:+UseG1GC -Xms512m -Xmx512m -XX:G1ReservePercent=10 -Xlog:gc*
 */
public class AllocationPacingDemo {

    // Retain some objects to prevent immediate reclamation
    private static final List<byte[]> SURVIVING_OBJECTS = new ArrayList<>();

    public static void main(String[] args) throws InterruptedException {
        System.out.println("Starting high-throughput allocation churn...");

        for (int i = 0; i < 10_000; i++) {
            // Allocate 1 MB chunks rapidly
            byte[] allocation = new byte[1024 * 1024];

            // Retain 10% of objects to fill Old Generation
            if (i % 10 == 0) {
                SURVIVING_OBJECTS.add(allocation);
            }

            // Simulate high-frequency allocation loop without artificial sleep
            if (i % 500 == 0) {
                System.out.printf("Allocated %d MBs, Retained items: %d\n", 
                                  i, SURVIVING_OBJECTS.size());
            }
        }
        System.out.println("Allocation complete.");
    }
}
```

---

3. 🧠 The "Deep Dive" (For the Interview):

### Technical Mechanics: G1 vs. ZGC

#### 1. Garbage-First (G1) Memory Pacing & Evacuation Failure
- **Adaptive IHOP (Initiating Heap Occupancy Percent):** G1 dynamically calculates when to start a concurrent marking cycle based on allocation velocity.
- **Pacing Mechanism:** If allocation rate spikes, G1 triggers thread pacing inside `G1AllocRegion`. The thread trying to allocate is stalled while the JVM attempts to reclaim regions.
- **Evacuation Failure:** If G1 runs out of free regions while evacuating live objects during a Young/Mixed GC, it falls back to **Evacuation Failure**. It must preserve objects in-place, dirty the card table, and—if memory is completely exhausted—trigger a Stop-The-World (STW) **Full GC**.

#### 2. Z Garbage Collector (ZGC) Allocation Pacing (`ZAllocationPacer`)
- **Sub-Millisecond Target:** ZGC aims for sub-millisecond STW pause times. To maintain this, it avoids falling back to Full GC at all costs.
- **The Pacer Engine:** ZGC tracks the historical allocation rate (bytes/second) and the velocity of concurrent mark/relocate phases.
- **Micro-Budgeting:** If available memory dips below a safety threshold, `ZAllocationPacer` assigns a "budget limit" to allocating threads. A thread requesting $N$ bytes is forced to stall in a micro-sleep loop (`os::naked_sleep`) for a duration computed as:
  $$\text{Delay} = \frac{\text{Requested Bytes}}{\text{Pacing Rate}}$$
- **Allocation Stall:** If the dynamic buffer hits 0 bytes, the thread enters an un-paced `Allocation Stall`, parking on a monitor until a ZGC page is reclaimed.

---

### Trade-Offs Matrix

| Strategy | Advantages | Trade-Offs / Disadvantages |
| :--- | :--- | :--- |
| **G1 Reserve Percent & IHOP** | High overall application throughput under standard steady-state workloads. | Prone to severe tail-latency spikes (STW Full GC) if allocation spikes exceed reserve limits. |
| **ZGC Allocation Pacing** | Smooths out latency; prevents catastrophic Stop-The-World pauses under memory stress. | Latency is shifted into application threads. Individual user requests take longer without explicit GC pause logs showing it. |

---

### Interviewer Probe Questions & Answers

#### Q1: "Your application latency spiked to 2 seconds, but the GC logs report maximum STW pause times of only 0.5ms using ZGC. What could be happening?"
**Answer:** The application is likely suffering from **Allocation Pacing or Allocation Stalls**. In ZGC, thread-level pacing delays happen *inside user thread execution context* during memory allocation slow-paths, not during GC safepoints. Therefore, standard GC pause time metrics won't reflect this delay. To verify, check ZGC logs for `gc,pacing` tags or monitor native thread states for threads sleeping inside `ZAllocationPacer::pace()`.

#### Q2: "How does tuning `-XX:G1ReservePercent` impact G1 GC performance under high allocation churn?"
**Answer:** `G1ReservePercent` (default 10%) sets the percentage of false-ceiling heap space kept empty as a safety buffer for object evacuations. Increasing this parameter (e.g., to 15-20%) reduces usable heap size for normal allocations, but provides a larger cushion against allocation spikes—reducing the risk of Evacuation Failures and STW Full GCs at the cost of requiring a larger overall heap.

#### Q3: "What parameters would you tune in ZGC to eliminate or reduce Allocation Stalls under bursty traffic?"
**Answer:**
1. **Increase Heap Size (`-Xmx`):** The primary fix for ZGC allocation stalls.
2. **Increase GC Concurrent Threads (`-XX:ConcGCThreads`):** Gives more CPU resources to ZGC phases so memory is reclaimed faster.
3. **Adjust Spike Tolerance (`-XX:ZAllocationSpikeTolerance`):** (Default 2.0). Increasing this multiplier tells ZGC to expect steeper allocation spikes and start concurrent collection earlier.

---

4. ✅ Summary Cheat Sheet:

### 3 Key Takeaways
1. **Pacing Shifts Latency:** Modern GCs handle extreme memory pressure by penalizing *allocating threads* with micro-delays, preserving global system availability over single-thread latency.
2. **Stalls $\neq$ STW Pauses:** An Allocation Stall pauses individual application threads waiting for memory; it does **not** show up as a Stop-The-World GC pause.
3. **Collection Speed vs. Allocation Speed:** If Object Creation Speed > Object Collection Speed, the system *must* either slow down allocations (Pacing), pause threads (Stalls), or halt the JVM (Full GC).

### 1 Golden Rule
> *"Zero GC pause time does not mean zero GC latency impact—when memory runs out, latency shifts from the Janitor (GC STW pause) to the Cook (Thread Allocation Pacing)."*