---
title: Stack Chunk Slicing and Continuation Suspension: The Memory Engine Behind Virtual Threads
date: 2026-09-01T04:46:52.668862
---

# Stack Chunk Slicing and Continuation Suspension: The Memory Engine Behind Virtual Threads

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
Traditional Java (Platform) Threads are tightly coupled to Operating System (OS) threads. The OS allocates a **massive, fixed-size memory block (typically 1MB)** for every thread's call stack—regardless of whether that thread is executing a complex calculation or just sleeping.

Virtual Threads decouple execution from the OS by moving thread call stacks into the **JVM Heap**. Instead of reserving megabytes of flat memory upfront, the JVM treats the call stack as dynamic data chunks (`StackChunk` objects) that grow, shrink, freeze, and thaw on demand.

```
OS Platform Thread: [ 1 MB Fixed Pre-allocated Stack ] (Reserved upfront)
Virtual Thread:     [ 200–400 Bytes Initial Metadata ] -> Expands/Shrinks on Heap
```

#### Real-World Analogy
Imagine a restaurant where every customer must be assigned a fixed, heavy wooden table (OS Thread Stack) that takes up $100\text{ sq ft}$, even if a customer only orders an espresso. You can only fit 50 tables before running out of floor space.

Virtual Threads are like a standing espresso bar with a dynamic coat-check room. When you step up to order, you use a tiny slip of paper (a dynamic stack chunk). If you have to wait 10 minutes for your pastry, the staff pins your slip to a bulletin board (freezes stack to heap) and frees up the counter space. When your pastry is ready, they hand you back your slip (thaw stack) to finish your meal.

#### Why Should I Care?
- **No More `OutOfMemoryError: unable to create native thread`**: You can spawn 1,000,000 Virtual Threads using only a few hundred megabytes of heap instead of 1 Terabyte of OS RAM.
- **Efficient Deep Call Stacks**: Frameworks like Spring and Hibernate create call stacks 50+ frames deep. The JVM only allocates heap memory for the frames currently in use.

---

### 2. 🛠️ How it Works (Step-by-Step)

When a Virtual Thread executes and hits a blocking operation (like I/O or a lock), it undergoes **Continuation Suspension**.

```
+-------------------------------------------------------------------------+
| STEP 1: EXECUTION                                                       |
| Carrier Thread (OS Stack) runs Virtual Thread code                      |
+-------------------------------------------------------------------------+
                                   │
                                   ▼ (Hits Blocking I/O: Socket.read())
+-------------------------------------------------------------------------+
| STEP 2: FREEZE (Stack Chunk Slicing)                                    |
| HotSpot VM unmounts Virtual Thread; active execution frames on the OS   |
| stack are sliced and copied into heap-allocated 'StackChunk' objects.   |
+-------------------------------------------------------------------------+
                                   │
                                   ▼ (Carrier Thread freed for other tasks)
+-------------------------------------------------------------------------+
| STEP 3: ASYNC NOTIFICATION                                              |
| JVM Network Poller / epoll detects socket ready                         |
+-------------------------------------------------------------------------+
                                   │
                                   ▼
+-------------------------------------------------------------------------+
| STEP 4: THAW (Lazy Frame Restoration)                                   |
| Carrier Thread re-claims Virtual Thread; top frames are copied back     |
| using 'Return Barriers' to lazily reload parent frames as needed.       |
+-------------------------------------------------------------------------+
```

#### Code Example: Observing Stack Depth and Memory Behavior

```java
package concurrency.internals;

import java.time.Duration;
import java.util.concurrent.Executors;

public class StackChunkDemo {

    public static void main(String[] args) throws InterruptedException {
        // Spawning 100,000 virtual threads that hold deep call frames while blocking
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 100_000; i++) {
                final int taskId = i;
                executor.submit(() -> deepCallStack(taskId, 30)); // 30 frames deep
            }
        } // Executor.close() waits for all threads to complete
    }

    private static void deepCallStack(int id, int depth) {
        if (depth > 0) {
            // Recurse to build execution stack frames
            deepCallStack(id, depth - 1);
        } else {
            // Leaf node: Thread freezes here; stack frames are sliced and written to Heap
            simulateIoWait();
        }
    }

    private static void simulateIoWait() {
        try {
            // Triggers Continuation.yield() inside Virtual Thread scheduler
            Thread.sleep(Duration.ofMillis(100));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### 1. HotSpot Internal Mechanics: `jdk.internal.vm.Continuation`
Under the hood, a Virtual Thread is a `Thread` wrapper around a `Continuation`.
- When blocking I/O occurs, Java calls `Continuation.yield(VTHREAD_SCOPE)`.
- The JVM executes a C++ runtime routine (`Continuation::freeze`) that walks the physical OS carrier stack from the current frame down to the continuation entry frame.
- **Stack Chunk Allocation**: The JVM allocates a `jdk.internal.vm.StackChunk` instance in **Young Gen (Eden)** and copies the frame descriptors, local variables, and operand stacks into it.

#### 2. The Performance Secret: Lazy Thawing via Return Barriers
Copying 50 stack frames back to the OS stack on every unblock would destroy CPU cache and throughput. The JVM uses **Lazy Stack Restoration**:
1. When a virtual thread resumes, the JVM only thaws the **immediate top frame(s)** needed for execution.
2. The JVM installs a **Return Barrier** (a specialized assembly stub / trap) at the bottom of the restored frame.
3. When the method returns, the CPU hits the barrier stub, which triggers an interrupt into the VM runtime to thaw the *next* parent frame from the heap `StackChunk`.

```
[ Carrier OS Stack ]                 [ JVM Heap: StackChunk ]
┌─────────────────────────┐          ┌─────────────────────────┐
│ Frame 30 (Active Frame) │ ◄────────┤ Frame 30                │
├─────────────────────────┤ (Thawed) ├─────────────────────────┤
│ [ RETURN BARRIER TRAP ] │          │ Frame 29 (Suspended)    │
└─────────────────────────┘          ├─────────────────────────┤
                                     │ Frame 28 (Suspended)    │
                                     └─────────────────────────┘
```

#### Trade-offs: OS Thread Stack vs. Virtual Thread Stack Chunks

| Dimension | Platform (OS) Thread | Virtual Thread |
| :--- | :--- | :--- |
| **Stack Allocation** | Contiguous virtual memory (1MB) | Dynamically sized `StackChunk` on Heap |
| **Context Switch Cost** | OS Kernel interrupt + CPU register swap | User-space frame copy to/from Heap |
| **GC Pressure** | Zero GC overhead | **High GC allocation rate** (Millions of short-lived `StackChunk` objects in Eden) |
| **Deep Recursion** | Causes `StackOverflowError` quickly | Consumes Heap RAM; GC overhead increases |

---

### Interviewer Probes (Tricky Edge Cases)

#### Probe 1: "Why do Virtual Threads increase Young Generation GC pressure even if my business code creates zero objects?"
> **Answer:** When millions of Virtual Threads block and unblock, `Continuation.freeze` creates `StackChunk` objects directly in the JVM Young Generation (Eden space). Context-switching is no longer a pure CPU operation—it is a **memory-allocation-heavy** operation. Tuning `NewRatio` or using generational ZGC/Shenandoah helps mitigate GC pauses caused by stack chunk churn.

#### Probe 2: "What happens to the stack chunk engine when code calls a JNI method or enters a `synchronized` block before blocking?"
> **Answer:** The stack becomes **Pinned**. The JVM cannot copy native C/C++ stack frames or frames holding native object monitors (`synchronized`) into Java Heap `StackChunk` structures. As a result, the Virtual Thread cannot yield; the underlying OS Carrier Thread remains blocked, temporarily negating the scalability benefits of Project Loom.

#### Probe 3: "How does the JVM prevent stack-copy amplification when a virtual thread has a call stack 100 frames deep?"
> **Answer:** Through **Lazy Thawing and Return Barriers**. The JVM does not copy all 100 frames back onto the Carrier stack at once. It only restores the topmost active frame and places a Return Barrier trap. Parent frames are lazily pulled back into the carrier stack one by one as methods execute their `return` instructions.

---

### 4. ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Dynamic vs. Fixed**: Virtual Threads eliminate the 1MB pre-allocated OS stack by storing call stacks as dynamic `StackChunk` objects in the JVM Heap.
2. **Freeze & Thaw**: Yielding freezes execution frames to the heap; resumption uses **Return Barriers** to lazily restore parent frames on demand.
3. **Allocation Overhead**: High-frequency virtual thread context switching shifts the performance bottleneck from OS thread scheduling to JVM **Young Gen garbage collection**.

#### 1 Golden Rule
> *"Virtual threads make concurrency cheap in OS memory, but they turn context switches into heap allocations—keep your call stacks clean, avoid thread pinning, and size your JVM Young Generation accordingly."*