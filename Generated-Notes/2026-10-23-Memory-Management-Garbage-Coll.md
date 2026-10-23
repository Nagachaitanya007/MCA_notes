---
title: Evacuation Failure & To-Space Exhaustion: Tuning Heap Headroom to Prevent Full GC Fallbacks
date: 2026-10-23T04:48:29.619839
---

# Evacuation Failure & To-Space Exhaustion: Tuning Heap Headroom to Prevent Full GC Fallbacks

---

### 1. 💡 The "Big Picture" (Plain English)

Modern garbage collectors like G1, Shenandoah, and ZGC are **evacuating collectors**. To clean memory without fragmenting it, they don't just erase dead objects in place—they pick up the surviving live objects from fragmented memory blocks and copy (**evacuate**) them into pristine, empty memory blocks called **"To-Space."**

**Evacuation Failure** (or **To-Space Exhaustion**) occurs when the garbage collector picks up an object to move it, looks around for an empty destination block, and discovers **there is nowhere left to put it**.

```
                MUTATOR THREADS                      GC EVACUATION THREAD
           (Pouring water into bucket)           (Trying to bail water out)
                       │                                     │
                       ▼                                     ▼
             ┌───────────────────┐                 ┌───────────────────┐
             │ Rapid Allocations │                 │ Moving Survivors  │
             └─────────┬─────────┘                 └─────────┬─────────┘
                       │                                     │
                       └───────────────┬─────────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │    FREE REGIONS REACH ZERO    │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       💥 TO-SPACE EXHAUSTED!
                          Emergency Stop-The-World
                          Full GC Fallback Triggered
```

#### The Real-World Analogy
Imagine you are renovating a crowded hotel floor by floor. 
* To renovate Room A, you must first move its paying guests into an empty, clean room on the same floor (the **To-Space**).
* You successfully evacuate rooms until suddenly the front desk checks in a massive busload of tourists who book every single spare room in the entire hotel.
* Now, you enter Room B to move the occupant, but **every single room in the hotel is occupied**. 
* You cannot complete the renovation. You are forced to sound the emergency fire alarm, freeze everyone in the hallways, and manually sort out the entire hotel from top to bottom before anyone can take another step.

#### Why Should You Care?
When your application runs out of evacuation headroom, your 5-millisecond GC pause budget instantly explodes into a **multi-second (or multi-minute) Stop-The-World (STW) Full GC**. This failure mode is responsible for sudden p99/p999 latency cliff-edges, severed database connections, dropped WebSocket sessions, and Kubernetes health-check timeouts that kill otherwise healthy containers.

---

### 2. 🛠️ How it Works (Step-by-Step)

```
[ Normal State ]
[Region A: Live + Dead] ──Evacuate Live──► [Region C: Clean To-Space] ✅
                                            (Free Regions Available)

[ Exhaustion State ]
[Region A: Live + Dead] ──Evacuate Live──► ❌ NO FREE REGIONS LEFT!
        │
        ├── 1. Allocation burst consumes Free Region List.
        ├── 2. Evacuation thread fails to acquire destination PLAB.
        ├── 3. Fallback: Self-forwarding pointers written to headers.
        └── 4. Emergency: Single-threaded / Parallel STW Full GC invoked.
```

#### The Step-by-Step Mechanism

1. **Concurrent Allocation & Evacuation:** Application threads (*mutators*) keep creating new objects in young regions while GC worker threads copy surviving objects into new survivor or tenured regions.
2. **Buffer Depletion:** If mutators allocate memory faster than GC workers can evacuate it, the pool of unallocated regions (the *Free Region List*) drops to zero.
3. **Allocation Failure in To-Space:** An evacuation worker asks the heap for a new Promotion Local Allocation Buffer (PLAB) or single-object slot to land an evacuating object, but the allocator returns `null`.
4. **Self-Forwarding (The Damage Control Phase):** Because the object cannot be moved, the GC leaves the object where it is and points the object’s own header back to itself (**self-forwarding**). It marks the region as un-evacuated.
5. **The Catastrophic Fallback:** Because the region layout is now corrupted and fragmented, the concurrent cycle aborts. The JVM halts all application threads and invokes an emergency, STW **Full GC** (historically single-threaded in older JVMs, multi-threaded in modern ones) to compact the entire heap via mark-sweep-compact.

#### Reproducing & Tuning Against Evacuation Failure

The following code generates a steady allocation rate punctuated by sudden micro-bursts, which frequently causes to-space exhaustion under default G1 settings:

```java
import java.util.ArrayDeque;
import java.util.Queue;

public class EvacuationFailureSimulator {
    // Retains long-lived objects to fill up Old Generation
    private static final Queue<byte[]> survivorBacklog = new ArrayDeque<>();

    public static void main(String[] args) throws InterruptedException {
        System.out.println("Starting allocation workload...");

        while (true) {
            // 1. Simulate steady background allocation
            for (int i = 0; i < 50; i++) {
                survivorBacklog.add(new byte[64 * 1024]); // 64 KB
                if (survivorBacklog.size() > 5000) {
                    survivorBacklog.poll(); // Maintain rolling footprint
                }
            }

            // 2. Simulate a sudden spike that exhausts available To-Space regions
            // If GC is actively evacuating when this hits, To-Space will collapse.
            allocateBurst();

            Thread.sleep(10);
        }
    }

    private static void allocateBurst() {
        byte[][] spike = new byte[200][];
        for (int i = 0; i < spike.length; i++) {
            spike[i] = new byte[512 * 1024]; // 512 KB per object
        }
    }
}
```

#### JVM Diagnostic & Tuning Flags

Run with logging enabled to see the exact moment To-Space is exhausted:

```bash
# 1. Observe the failure signature
java -Xms2g -Xmx2g \
     -Xlog:gc*,gc+phases=debug:file=gc.log:time,uptime,pid:filecount=5,filesize=100M \
     EvacuationFailureSimulator
```

Look for this telltale warning in `gc.log`:
```text
[0.852s][info][gc] GC(14) Pause Young (Normal) (G1 Evacuation Pause)
[0.854s][info][gc] GC(14) To-space exhausted
[0.855s][info][gc] GC(14) Evacuation Failure: 12.4ms
...
[0.860s][info][gc] GC(15) Pause Full (G1 Compaction Pause) 1840M->412M(2048M) 1420.312ms
```

To prevent this, tune the **cushion** and the **trigger threshold**:

```bash
# 2. Production Tuning Remediation
java -Xms4g -Xmx4g \
     -XX:+UseG1GC \
     -XX:InitiatingHeapOccupancyPercent=40 \  # Start concurrent marking earlier (default is 45)
     -XX:G1ReservePercent=15 \               # Reserve 15% of heap strictly as false-floor To-Space (default is 10)
     -XX:G1ReservePercent=15 \
     -XX:SurvivorRatio=6 \                   # Expand survivor capacity relative to Eden
     -Xlog:gc*:file=gc_tuned.log \
     EvacuationFailureSimulator
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Internal Mechanics of Self-Forwarding
When an evacuation thread determines that an object cannot be moved:

1. **Mark Word Manipulation:** In normal evacuation, when Object A moves to Address B, Object A's Mark Word in its object header is rewritten with a forwarding pointer containing Address B. If no memory is available, the JVM writes Object A's **own address** into its Mark Word (`Self-Forwarded` state).
2. **Phase Retracing:** Once the GC realizes one or more objects have failed evacuation, it cannot simply free the source regions. It must run an expensive **post-evacuation fixup phase**:
   * It scans all modified references in the Remembered Sets (RSets) and thread stacks.
   * Any pointer pointing to a self-forwarded object must remain pointed at the original source region.
   * Regions containing self-forwarded objects are converted from "Evacuation Candidates" into "Retained Old Regions."

```
Normal Evacuation:
[Obj Header | Ptr -> New_Addr] ──────────► [Copied Obj at New_Addr]

Evacuation Failure (Self-Forwarding):
[Obj Header | Ptr -> Self_Addr] (Object pinned in place; region cannot be cleared)
```

#### Why Adaptive IHOP (Initiating Heap Occupancy Percent) Fails
Modern collectors use dynamic predictors (`-XX:+G1UseAdaptiveIHOP`) that calculate:
$$\text{Threshold} = \text{Heap Capacity} - (\text{Allocation Rate} \times \text{Marking Cycle Duration})$$

If your workload produces a non-linear, bimodal allocation profile (e.g., quiet periods interrupted by sudden JSON/batch processing spikes), the rolling average model fails:
* The historical allocation rate prediction is calculated during low-traffic periods.
* The burst arrives.
* The GC starts the concurrent cycle too late.
* The mutators overrun the available free regions before concurrent marking finishes, triggering **To-Space Exhaustion**.

#### Trade-Off Analysis

| Tuning Action | Low-Latency Benefit | System-Level Trade-Off |
| :--- | :--- | :--- |
| **Increase `-XX:G1ReservePercent`** (e.g., 10% $\to$ 20%) | Adds a larger safety buffer, preventing evacuation failure during allocation bursts. | Artificially reduces the usable heap for application mutators, triggering GCs *more frequently*. |
| **Lower `-XX:InitiatingHeapOccupancyPercent`** (e.g., 45% $\to$ 35%) | Starts concurrent mark cycles much earlier, ensuring old regions are reclaimed ahead of time. | Consumes more background CPU cycles for concurrent marking threads; may lower application throughput. |
| **Increase `-XX:ConcGCThreads`** | Finishes concurrent marking faster, reducing the window during which to-space can be exhausted. | Steals CPU cores directly from mutator (application) threads, increasing request processing latency. |

---

### Interviewer Probe Questions

#### 1. "We saw `To-space exhausted` in the GC logs, but latency only spiked by 40ms instead of 3 seconds. Did we avoid a Full GC?"
**Answer:** Yes. A To-Space exhaustion does not *always* immediately trigger a Full GC. If the JVM can resolve the evacuation failure simply by keeping the un-evacuated objects in place via self-forwarding pointers and the application still has sufficient free regions to continue running, it will complete a **Partial Evacuation Failure Recovery**. 

However, this still causes a latency spike because the GC must pause longer to scan the un-evacuated regions, restore the object mark words, and reset the internal card tables. A Full GC is only avoided if the mutators have enough headroom to keep allocating after this extended pause finishes.

#### 2. "Why can Humongous Object allocations trigger an Evacuation Failure even when the total heap utilization is only 50%?"
**Answer:** Region-based collectors like G1 require Humongous Objects (objects larger than 50% of a region size) to be allocated in **contiguous sequences of regions**. 

If the heap is 50% free, but the free regions are scattered across the memory space rather than arranged contiguously (external fragmentation), an allocation request for a contiguous 3-region block will fail. To satisfy this request, G1 is forced to run an emergency Garbage Collection cycle to free up space. If free regions are pinned or the free list is fragmented, the collector encounters to-space exhaustion despite plenty of total bytes being free.

#### 3. "How does ZGC prevent the catastrophic Evacuation Failure that plagues G1?"
**Answer:** ZGC uses **load-value barriers and colored pointers** to decouple object access from physical relocation. 

If ZGC runs out of memory during an evacuation phase, it does not immediately drop to a STW Full GC compaction algorithm. Instead, it enters an **Allocation Stall**: mutator threads trying to allocate are throttled or temporarily blocked at the allocator level until concurrent GC cycles free up pages. While this increases tail latency for the allocating threads, it prevents a global Stop-The-World pause across non-allocating threads.

---

### 4. ✅ Summary Cheat Sheet

* **Evacuation Failure = To-Space Depleted:** Occurs when an evacuating GC worker cannot allocate destination memory to move a surviving object.
* **The Log Signature:** Always search for `"to-space exhausted"` or `"Evacuation Failure"` in GC logs to diagnose sudden, inexplicable p99 latency cliffs.
* **Self-Forwarding Overhead:** Even if an evacuation failure does not drop into a Full GC, the restoration of self-forwarded headers causes severe pause degradation.

> **The Golden Rule:** If you see `To-space exhausted` under bursty workloads, **raise `-XX:G1ReservePercent`** (give the GC a bigger emergency buffer) and **lower `-XX:InitiatingHeapOccupancyPercent`** (trigger cleanups earlier)—never just increase `-Xmx` without adjusting these thresholds.