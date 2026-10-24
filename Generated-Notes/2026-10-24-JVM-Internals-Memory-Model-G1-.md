---
title: JVM G1 GC: Remembered Sets (RSets) and Cross-Region Reference Tracking
date: 2026-10-24T04:48:47.846773
---

# JVM G1 GC: Remembered Sets (RSets) and Cross-Region Reference Tracking

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
The Garbage-First (G1) collector divides your heap into thousands of equal-sized chunks called **Regions**. To clean up just one region without freezing the entire application to check every object in the heap, G1 must know: *"Which objects in other regions are pointing to objects in this region?"* 

The **Remembered Set (RSet)** is that incoming contact book. Every single region has its own RSet that records all external locations pointing into it.

```
Traditional GC (Points-Out): "I am Card 42, and I point to someone else."
G1 RSet (Points-Into):        "I am Region B, and Card 42 from Region A points to me."
```

#### Real-World Analogy
Imagine an apartment building where every tenant has an **inbox log** posted outside their door. 
* In a traditional system, if you want to know who is talking to Alice in Room 201, you would have to walk through the entire building, knocking on every door from Room 1 to Room 500, asking: *"Are you talking to Alice?"*
* With G1's RSet, Alice's door has a clipboard that logs: *"Bob in Room 104 and Carol in Room 305 sent letters here."* 
* When it is time to inspect Alice’s room, the inspector only needs to check Alice's room and verify letters with Bob and Carol. No one else in the building is disturbed.

#### Why should I care? What problem does it solve today?
1. **Low, Predictable Latencies:** G1 can collect a small subset of regions (the Collection Set, or CSet) in 10ms instead of stopping the world for 2 seconds to scan the entire 32GB heap.
2. **Diagnosing GC Pauses:** In your GC logs, if you see high times under `Update RS` or `Scan RS`, your application is suffering from heavy cross-region object mutations or RSet bloating.
3. **Preventing Native Memory Bloat:** RSets live in **native memory**, not the Java heap. In pointer-heavy applications, RSets can quietly consume an extra **10% to 20% of your total RAM**, leading to mysterious Linux Out-Of-Memory (`oom-killer`) process terminations.

---

### 2. 🛠️ How it Works (Step-by-Step)

Cross-region tracking is maintained dynamically through a cooperative pipeline between application threads (mutators) and background GC threads.

```
[Mutator Thread] ──(writes pointer)──> [Post-Write Barrier]
                                              │
                                     Marks Card Dirty & Pushes
                                              ▼
                                   [Dirty Card Queue (DCQ)]
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         [Concurrent Refinement Threads]                   [Mutator Handshake]
             (Normal: Green/Yellow Zone)                   (Overloaded: Red Zone)
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                                 [Target Region's RSet]
                                 (Sparse ➔ Fine ➔ Coarse)
```

#### Step-by-Step Execution:
1. **Mutator Mutation:** A running thread executes `objA.field = objB`, where `objA` lives in Region 1 and `objB` lives in Region 2.
2. **Post-Write Barrier:** The JIT-compiled write barrier executes immediately after the pointer store. It identifies the 512-byte memory slice (**Card**) in Region 1 where `objA` lives, marks it as "dirty" in the global Card Table, and enqueues that card index into a thread-local buffer called the **Dirty Card Queue (DCQ)**.
3. **Queue Handoff:** When a thread's local DCQ fills up, it is transferred to a global buffer list.
4. **Concurrent Refinement:** Background threads (`G1ConcurrentRefineThread`) wake up, take buffers from the global list, read the dirty cards, inspect the actual references on the heap, and register Region 1's card inside **Region 2's Remembered Set**.
5. **Collection Time (Evacuation):** When G1 collects Region 2, it treats all entries in Region 2's RSet as extra **GC Roots**. It never scans Region 1.

#### Demonstrating RSet Overhead in Code

The following snippet creates a data structure that triggers significant cross-region references, causing G1 RSets to expand into native memory:

```java
import java.util.ArrayList;
import java.util.List;

/**
 * Run with:
 * -XX:+UseG1GC -Xms2g -Xmx2g -XX:G1HeapRegionSize=1m
 * -Xlog:gc*,gc+phases=debug,gc+remset=trace:file=gc.log:time,uptime,pid:filecount=5,filesize=100m
 */
public class RSetPressureDemo {
    // Array of old-generation anchors
    private static final List<Object[]> OLD_CONTAINERS = new ArrayList<>();

    public static void main(String[] args) throws InterruptedException {
        System.out.println("Allocating base objects to fill old generation regions...");

        // 1. Create many large arrays that get promoted to Old Regions
        for (int i = 0; i < 1000; i++) {
            OLD_CONTAINERS.add(new Object[1024]); 
        }

        System.out.println("Creating high-frequency cross-region pointer links...");

        // 2. Cross-link objects across different regions.
        // Each assignment crosses region boundaries, forcing G1 to allocate
        // PRT (Per-Region Table) entries inside the target regions' RSets.
        long counter = 0;
        while (counter < 50_000_000) {
            int sourceIndex = (int) (counter % OLD_CONTAINERS.size());
            int targetIndex = (int) ((counter + 17) % OLD_CONTAINERS.size());

            Object[] source = OLD_CONTAINERS.get(sourceIndex);
            Object[] target = OLD_CONTAINERS.get(targetIndex);

            // Mutation: Store reference from source region into target region
            // Triggers: Post-Write Barrier -> Card Table Dirtied -> DCQ -> RSet Update
            source[(int) (counter % source.length)] = target;

            counter++;
            if (counter % 5_000_000 == 0) {
                System.out.println("Interlinked pointers: " + counter);
                Thread.sleep(100);
            }
        }
    }
}
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Core Mechanism: Points-Into Accounting
Traditional collectors (like CMS or Parallel Old) use a standard **Points-Out** Card Table:
* A byte array where 1 byte corresponds to 512 bytes of heap space.
* If an old object changes, you mark the byte dirty. During GC, you must scan the *entire* card table to find dirty cards.

G1 cannot afford to scan the entire card table because it collects a dynamic subset of regions. Therefore, G1 turns the relationship inside out: **Points-Into**. Each region must store a list of all external cards pointing into it.

Because storing exact card addresses for every single pointer would consume more memory than the actual data, G1 uses a **Three-Tier Adaptive Per-Region Table (PRT)** to store cards inside an RSet:

```
[Target Region RSet]
  │
  ├── 1. Sparse PRT: Direct Hash Array of Card Indices
  │      (Low memory: Used when only 1-8 cards point here)
  │
  ▼ [Capacity Exceeded -> Promoted]
  ├── 2. Fine PRT: Hash Map of (Source Region -> BitMap)
  │      (Medium memory: 1 bit = 1 specific 512-byte card in source region)
  │
  ▼ [Too Many Regions Point Here -> Promoted]
  └── 3. Coarse PRT: Global BitMap of Region Indices
         (1 bit = 1 Entire Region. Lost card precision!)
```

1. **Sparse PRT:** An array of specific card indexes. If Region A has only 3 cards pointing into Region B, Region B’s RSet stores them in a compact hash table.
2. **Fine PRT:** When the Sparse PRT overflows, it upgrades to a Fine PRT. This is an open-hash table mapping `Region Address -> BitMap`. Each bit represents one 512-byte card inside that source region.
3. **Coarse PRT:** If thousands of regions point into Region B, storing bitmaps for each region would exhaust native memory. G1 upgrades them to a Coarse BitMap. In this mode, **1 bit represents an entire Region**. 
   * *The Penalty:* When Region B is collected, G1 must scan the **entire source region**, not just a single card!

#### Concurrent Refinement & Pacing Zones
Mutator threads generate dirty cards at runtime. If background refinement threads (`G1ConcRefinementThreads`) cannot keep up, dirty cards pile up, threatening to blow up pause times during the STW phase. G1 solves this with **Zoned Pacing**:

* **Green Zone (`-XX:G1ConcRefinementGreenZone`):** Background threads sleep. The queue is small; processing is deferred.
* **Yellow Zone (`-XX:G1ConcRefinementYellowZone`):** Background refinement threads wake up and actively drain the DCQ concurrently with application execution.
* **Red Zone (`-XX:G1ConcRefinementRedZone`):** The background threads are falling behind. **Mutator threads are forced to process their own dirty cards directly.** Your application threads halt their business logic and do GC maintenance work, preventing queue explosion at the cost of application thread latency.

#### What are the trade-offs?
* **Latency vs. Memory:** RSets grant predictable sub-10ms collection pauses, but they do it by stealing native RAM (C++ heap). In caches with millions of random object references, RSets can take up to 20% of your total process memory.
* **Coarsening vs. Scanning:** Coarse bitmaps prevent RSet out-of-memory errors, but cause sudden spikes during the `Scan RS` phase because entire 1MB–32MB regions must be scanned from top to bottom.

---

### Interviewer Probes (Tricky Questions)

#### 1. "Do Young regions have Remembered Sets tracking other Young regions?"
**Answer:** No. RSets are **never** maintained for `Young -> Young` references, nor are they maintained for `Old -> Young` references. 
* *Why?* Because G1 collects **all** Young regions during every single GC cycle (Young GC or Mixed GC). 
* Since the entire young generation is evacuated unconditionally, G1 will scan all young objects anyway. Maintaining RSets for young regions would waste CPU and native memory for references that will be collected in the immediate next pause.
* RSets *only* track: `Old -> Young` (transiently via dirty card queues) and `Old -> Old` (fully refined).

#### 2. "In our production GC logs, we noticed the `Update RS` phase takes 40ms out of a 50ms pause. What is happening under the hood, and how do we fix it?"
**Answer:** The `Update RS` phase is the time G1 spends draining the remaining unprocessed Dirty Card Queues (DCQs) that mutator threads left behind right before the safepoint began.
* **Root Cause:** Refinement threads (`G1ConcRefinementThreads`) are either starved of CPU, or the mutators are producing dirty cards faster than the background threads can refine them (mutators are breaching the Yellow/Red zones).
* **Fixes:**
  1. Increase refinement threads via `-XX:G1ConcRefinementThreads`.
  2. Lower `-XX:G1ConcRefinementGreenZone` and `YellowZone` to make threads start processing earlier.
  3. Increase `-XX:G1RSetUpdatingPauseTimePercent` (default is 10) to give G1 permission to adaptively pace concurrent buffers to fit your target pause goal.

#### 3. "What is RSet Coarsening, and what is its operational danger?"
**Answer:** RSet Coarsening is a fallback mechanism to prevent unbounded native memory growth. When too many distinct regions hold references to a target region, G1 stops tracking individual 512-byte cards (Fine PRT) and switches to a single bit representing the *entire source region* (Coarse PRT).
* **Danger:** The next time this target region is evacuated, G1 cannot inspect only the few dirty 512-byte cards; it must scan the **entirety** of all coarsened source regions to discover pointers. This leads to an immediate latency spike under the **`Scan RS`** phase of the GC pause.

---

### 4. ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Points-Into Architecture:** Unlike traditional collectors that track what a region points to, G1's RSet tracks what points *into* a region, allowing isolated, partial-heap collection.
2. **Three Memory Tiers:** RSets scale through **Sparse** (array of cards) $\rightarrow$ **Fine** (bitmap of cards per region) $\rightarrow$ **Coarse** (bitmap of regions) to balance native memory use against scanning overhead.
3. **Pacing Zones Control Mutators:** If dirty card generation outpaces refinement (Red Zone), application threads are hijacked to process GC cards themselves, causing mysterious latency spikes outside of safepoints.

#### 1 Golden Rule to Remember
> **"High `Update RS` means your background refinement threads are falling behind mutator writes; high `Scan RS` means your references are so fragmented across regions that your RSets have coarsened."**