---
title: JVM G1 Collector: Mixed GC Cycles, Adaptive IHOP, and Evacuation Failure
date: 2026-08-02T04:46:50.488237
---

# JVM G1 Collector: Mixed GC Cycles, Adaptive IHOP, and Evacuation Failure

1. 💡 The "Big Picture" (Plain English)
--------------------------------------

### What is this in simple terms?
The Garbage First (G1) collector divides your Java heap into thousands of equal-sized memory blocks called **Regions**. Unlike older collectors that stop everything to clean the entire "Old Generation" all at once, G1 cleans the Old Generation incrementally through **Mixed Garbage Collections**. 

During a Mixed GC, G1 cleans all Young regions *plus* a carefully chosen batch of Old regions that contain the highest amount of dead objects (the most "garbage first"). To pull this off without stalling your application, G1 relies on **Adaptive IHOP** (Initiating Heap Occupancy Percent) to predict when to start scanning the heap, and attempts to recover gracefully if memory fills up faster than it can clean—a crisis known as **Evacuation Failure**.

### Real-World Analogy: A Luxury Hotel's Housekeeping System
Imagine running a 1,000-room luxury hotel:

* **Young GC (Daily Room Cleaning):** Housekeepers daily clean rooms where guests just checked out (short-lived objects). It's quick and happens constantly.
* **Concurrent Marking (Hotel Auditor):** An auditor walks the hallways taking notes on which long-term resident suites (Old Generation) are messy or vacant, without kicking guests out.
* **Mixed GC (Targeted Deep Cleaning):** Instead of closing the entire hotel for a week to deep-clean every suite at once, the manager schedules deep cleans for 5–10 of the *dirtiest* suites alongside the daily room service each morning.
* **Adaptive IHOP (Smart Scheduling):** The manager uses historical booking data to start the room audit early if a massive tour bus is predicted to arrive soon.
* **Evacuation Failure (Overbooking Crisis):** A guest tries to check into a fresh suite, but housekeeping couldn't clean any suites fast enough. The manager must temporarily stall check-ins, move furniture around right in front of the guest, and clear space under extreme stress.

### Why should I care?
Understanding Mixed GCs and Evacuation Failure helps you solve the most common enterprise Java performance issues: random pause-time spikes and unexpected Full GCs under high load. By understanding these mechanics, you can tune G1 parameters intelligently rather than blindly adjusting heap size.

---

2. 🛠️ How it Works (Step-by-Step)
----------------------------------

### The Lifecycle of G1's Mixed Collection Cycle

```
[ Young GC Phase ] ---> [ Concurrent Marking Phase ] ---> [ Mixed GC Phase ]
       ^                                                         |
       |-------------------- (Repeat Cycle) ---------------------|
                                                                 |
                                              (If Heap Runs Out) V
                                                     [ Evacuation Failure ]
                                                     [  ---> Full GC   ]
```

1. **Young GC Cycle:** G1 continuously allocates objects into Young regions (Eden/Survivor) and cleans them using STW (Stop-The-World) Young GCs.
2. **IHOP Trigger:** When the total occupied Old Generation space exceeds the IHOP threshold (e.g., 45% of total heap), G1 triggers the **Concurrent Marking Cycle**.
3. **Concurrent Marking:** While application threads run, G1 traces object references across the heap to calculate exact garbage density for every Old region.
4. **Collection Set (CSet) Selection:** G1 sorts Old regions by garbage density and selects the top candidates that can be evacuated within your target pause time (`-XX:MaxGCPauseMillis`).
5. **Mixed GC Execution:** Over a series of multiple pause phases (`-XX:G1MixedGCCountTarget`), G1 evacuates live objects from Eden, Survivor, and the selected Old regions into fresh, empty destination regions ("To-Space").
6. **Evacuation Failure (Fallback):** If no empty "To-Space" region is available during evacuation, G1 aborts mixed evacuation, pins un-copied objects in place, self-forwards headers, and invokes an emergency Full GC.

### Demonstrating Heap Pressure and Evacuation Risk

Here is Java code designed to create short-lived churn alongside long-lived retained state—the exact scenario that strains G1 Mixed GCs:

```java
import java.util.ArrayList;
import java.util.List;

public class MixedGCDemo {
    // Retained Old Gen space (Long-lived objects)
    private static final List<byte[]> longLivedStore = new ArrayList<>();

    public static void main(String[] args) throws InterruptedException {
        System.out.println("Starting workload simulating G1 Mixed GC triggers...");

        // Phase 1: Build up Old Generation space to cross IHOP threshold
        for (int i = 0; i < 50; i++) {
            // Allocate 10MB chunks that survive Young GC and get promoted
            longLivedStore.add(new byte[10 * 1024 * 1024]);
            Thread.sleep(50); 
        }

        System.out.println("Old Generation populated. Starting high-churn Young allocations...");

        // Phase 2: Rapid allocation churn triggering Young & Mixed GCs
        for (int i = 0; i < 10_000; i++) {
            // High rate of short-lived allocations
            byte[] transientData = new byte[2 * 1024 * 1024]; 
            
            // Randomly replace old data to create "garbage" inside Old Generation regions
            if (i % 5 == 0 && !longLivedStore.isEmpty()) {
                int indexToReplace = (int) (Math.random() * longLivedStore.size());
                longLivedStore.set(indexToReplace, new byte[10 * 1024 * 1024]);
            }

            if (i % 100 == 0) {
                Thread.sleep(20);
            }
        }
        System.out.println("Workload complete.");
    }
}
```

*Run with flags to inspect G1 behavior:*
`java -XX:+UseG1GC -Xms512m -Xmx512m -Xlog:gc*,gc+ihop=debug MixedGCDemo`

---

3. 🧠 The "Deep Dive" (For the Interview)
-----------------------------------------

### 1. Adaptive IHOP Mechanics
Older G1 implementations used a static `-XX:InitiatingHeapOccupancyPercent=45`. Modern OpenJDK uses **Adaptive IHOP** (`-XX:+G1UseAdaptiveIHOP`, enabled by default).

Adaptive IHOP continuously measures two variables:
* **Allocation Rate:** How fast bytes are being allocated in the Young Generation (MB/s).
* **Marking Time:** How long the Concurrent Marking phase takes from start to finish (seconds).

```
Adaptive Threshold = Total Heap - (Allocation Rate * Marking Time) - Buffer Safety Margin
```

If your application's allocation rate accelerates suddenly, Adaptive IHOP dynamically lowers the threshold (e.g., from 45% down to 20%), initiating concurrent marking earlier to avoid running out of space before Mixed GC completes.

### 2. Collection Set (CSet) Selection Algorithm
During Mixed GC, G1 must choose which Old regions to evacuate without exceeding `-XX:MaxGCPauseMillis`.

```
                    ┌─────────────────────────────────────────┐
                    │      G1 Region Garbage Density          │
                    └─────────────────────────────────────────┘
 Region A (90% Dead)   Region B (70% Dead)   Region C (40% Dead)   Region D (5% Dead)
[🗑️🗑️🗑️🗑️🗑️🗑️🗑️🗑️🗑️💎] [🗑️🗑️🗑️🗑️🗑️🗑️🗑️💎💎💎] [🗑️🗑️🗑️🗑️💎💎💎💎💎💎] [🗑️💎💎💎💎💎💎💎💎💎]
        │                     │                     │                     │
        ▼                     ▼                     ▼                     ▼
 ─── Highest Efficiency ────────────────────────────────────── Lowest Efficiency ───
 [ Added to CSet ]     [ Added to CSet ]     [ Added to CSet ]     [ Excluded (>Waste%) ]
```

1. **Efficiency Calculation:** For each Old region, G1 calculates the live data size vs. total size ratio. Regions with high garbage density yield the highest reclaimed space for minimal CPU copy effort.
2. **Sorting & Filtering:** Regions with live data below `-XX:G1MixedGCLiveThresholdPercent` (default: 85%) are sorted by reclaimable space.
3. **Partitioning:** G1 splits the selected Old regions across `-XX:G1MixedGCCountTarget` (default: 8) successive mixed collection cycles.
4. **Waste Cutoff:** If the total reclaimable garbage drops below `-XX:G1HeapWastePercent` (default: 5%), G1 skips remaining mixed collections to avoid costly low-yield copying pauses.

### 3. Evacuation Failure Internals (To-Space Exhaustion)
An **Evacuation Failure** occurs when G1 attempts to move a live object from a source region into a destination region ("To-Space"), but no free regions exist in the heap.

```
       [ Source Region ]                       [ Heap Pool ]
  ┌────────────────────────┐              ┌────────────────────┐
  │ Live Object A [Header] │ ── Evacuate ─►│ NO FREE REGIONS!!  │
  └────────────────────────┘              └────────────────────┘
               │                                     │
               ▼                                     ▼
   [ Self-Forward Object A ]               [ Evacuation Failure ]
   (Set Mark Word Bit Mask)                (Stalls GC Thread)
               │                                     │
               └──────────────────┬──────────────────┘
                                  ▼
                     [ Fallback to Full GC ]
```

When this happens, G1 enters an emergency handling protocol:
1. **Thread Lock & Pinning:** The GC thread cannot copy the object. It cancels the evacuation for that object and **pins** it in its original region.
2. **Self-Forwarding:** G1 restores or alters the object's mark word header using a special bit mask pattern (Self-Forwarded State) so references still point to the object's original location.
3. **Region Poisoning:** Regions containing pinned/self-forwarded objects are marked as polluted. They cannot be reclaimed in this cycle.
4. **Full GC Trigger:** Because memory is exhausted and regions are fragmented, G1 aborts the Mixed GC and initiates a single-threaded or parallel Fallback **Full GC** (Serial/Parallel compaction pass over the whole heap), causing a massive pause-time spike.

---

### Trade-offs

| Strategy / Parameter | Pros | Cons / Overhead |
| :--- | :--- | :--- |
| **Adaptive IHOP** | Prevents unexpected Full GCs by predicting allocations dynamically. | Requires sampling cycles; can trigger false marking runs during temporary traffic bursts. |
| **Aggressive Mixed GC** (`G1MixedGCCountTarget=4`) | Reclaims Old Gen memory faster in fewer total pause blocks. | Increases individual GC pause durations; risks exceeding `MaxGCPauseMillis`. |
| **Relaxed Target Pause** (`MaxGCPauseMillis=500ms`) | Gives G1 larger time windows to clean more Old regions per cycle. | Increases application latency spikes; bad for strict SLA API endpoints. |

---

### Interviewer Probes (Tricky Questions & Winning Answers)

#### Question 1: "If G1 is designed to avoid Full GCs, why am I still seeing `to-space exhausted` and Full GCs in my GC logs?"
**Answer:** `to-space exhausted` (Evacuation Failure) occurs when the allocation rate into the heap exceeds G1's ability to evacuate regions, or when memory is too fragmented for object promotion. Common causes include:
1. Humongous allocations (objects $\ge 50\%$ of region size) fragmenting available contiguous regions.
2. The Adaptive IHOP starting concurrent marking too late due to a sudden, sudden burst of allocation traffic.
3. The GC pause target (`-XX:MaxGCPauseMillis`) being tuned too low, forcing G1 to evacuate too few Old regions per cycle, causing Old Gen to fill up faster than it is cleaned.

#### Question 2: "What is the exact purpose of `-XX:G1HeapWastePercent` during Mixed Collection?"
**Answer:** Cleaning Old regions has a diminishing return cost: copying regions that are 80% live objects consumes high CPU time for very little freed space. `-XX:G1HeapWastePercent` (default 5%) sets an acceptable threshold of uncollected garbage in Old regions. Once the total reclaimable space in remaining candidate regions drops below this percentage of total heap, G1 completely terminates the Mixed GC cycle, saving CPU cycles and latency budget.

#### Question 3: "What is the internal difference between a Young GC and a Mixed GC in G1?"
**Answer:** At the execution level, both use identical evacuation mechanisms (STW pauses moving live objects to target regions). The key difference lies in the **Collection Set (CSet)** composition:
* **Young GC:** CSet contains *only* Young regions (Eden + Survivor).
* **Mixed GC:** CSet contains *all* Young regions **plus** a selected subset of Old Generation regions chosen based on high garbage density metrics obtained during the Concurrent Marking phase.

---

4. ✅ Summary Cheat Sheet
------------------------

```
               ┌─────────────────────────────────────────┐
               │    G1 MIXED GC & IHOP CHEAT SHEET       │
               └─────────────────────────────────────────┘
  
  [ IHOP Trigger ]  ──► Calculates: Alloc Rate x Marking Time
  [ Marking Phase ] ──► Audits Heap -> Finds High Density Regions
  [ Mixed Phase ]   ──► Cleans Young + Top Dirtiest Old Regions
  [ To-Space Exhaust]─► No Empty Space -> Pins Objects -> FULL GC!
```

### 3 Key Takeaways
1. **Mixed GCs are incremental:** G1 never cleans all Old Gen regions at once; it spreads Old Gen evacuation across multiple pause cycles (`-XX:G1MixedGCCountTarget`).
2. **Adaptive IHOP is predictive:** G1 dynamically adjusts when to start marking based on allocation rate dynamics versus past marking duration.
3. **Evacuation Failure is expensive:** If G1 runs out of empty regions while copying live objects, it pins the objects, aborts evacuation, and drops into an expensive Full GC.

### 1 Golden Rule
> **"If G1 triggers frequent Full GCs, don't just add more heap—check for To-Space Exhaustion. Either increase `-XX:G1ReservePercent` (default 10%), give G1 more time budget via `-XX:MaxGCPauseMillis`, or initiate marking earlier by lowering `-XX:InitiatingHeapOccupancyPercent`."**