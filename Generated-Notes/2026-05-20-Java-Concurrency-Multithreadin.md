---
title: The Mechanics of Carrier Threads: How Virtual Threads Mount, Unmount, and Pin
date: 2026-05-20T04:46:18.441576
---

# The Mechanics of Carrier Threads: How Virtual Threads Mount, Unmount, and Pin

---

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Virtual Threads are incredibly lightweight, but they cannot run on the CPU directly. Under the hood, they need a real, heavy operating system (OS) thread to execute their instructions. This real OS thread is called a **Carrier Thread**. 

Think of a Virtual Thread as a passenger, and the Carrier Thread as a bus. When the passenger wants to travel (run code), they get on the bus (**Mounting**). When the passenger has to wait for something—like waiting at a customs checkpoint (blocking database call or API request)—they don't make the bus sit idle and block traffic. Instead, the passenger steps off the bus (**Unmounting**), and the bus immediately picks up another passenger. When the customs check is complete, the passenger gets back onto the next available bus to finish their journey.

### Why should I care?
If you write code that forces the passenger to lock themselves to their seat (e.g., using `synchronized` blocks or calling native C-libraries), the passenger cannot step off when blocked. The entire bus is forced to park and wait. 

This disaster is called **Thread Pinning**. If your Carrier Threads get pinned, your entire application will slow to a crawl, completely defeating the purpose of upgrading to Virtual Threads. Understanding how mounting and pinning work is what separates a developer who simply "uses" Virtual Threads from an engineer who knows how to design high-throughput, production-grade reactive systems.

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Lifecycle of a Virtual Thread Task

1. **Scheduling**: You submit a task to a Virtual Thread. The JVM places this task in a work queue.
2. **Mounting**: An internal JVM scheduler (a specialized `ForkJoinPool`) assigns an idle Carrier Thread to execute the Virtual Thread. The JVM copies the execution state (stack frames) of the Virtual Thread onto the Carrier Thread.
3. **Execution**: The code runs normally.
4. **Blocking (Yielding)**: The code hits a blocking operation (e.g., `SocketChannel.read()`). Instead of blocking the OS thread, the Virtual Thread **yields**:
   - The JVM copies its current stack frames off the Carrier Thread and onto the JVM **Heap**.
   - The Virtual Thread is marked as *parked*.
5. **Carrier Liberation**: The Carrier Thread is now free to mount a different Virtual Thread.
6. **Resuming**: When the I/O event finishes, the OS notifies the JVM. The Virtual Thread is put back in the scheduler's queue, eventually **mounting** onto *any* available Carrier Thread (not necessarily the original one) to resume execution.

### The Flow Visualized

```text
       [ Virtual Thread (VT) Queue ]
                     │
                     ▼ (Mounting)
 ┌──────────────────────────────────────┐
 │       Carrier Thread (Platform)      │ <── Runs VT code
 └──────────────────────────────────────┘
                     │
                     ├───────── Wait for Database / Network? ─────────┐
                     ▼ (Normal Unmount)                               ▼ (Pinning Block)
 ┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
 │       Carrier Thread (Platform)      │          │       Carrier Thread (Platform)      │
 │          [ Is now FREE ]             │          │          [ BLOCKED & STUCK ]         │
 └──────────────────────────────────────┘          └──────────────────────────────────────┘
                     │                                                │
                     ▼ (Saves State)                                  ▼
      [ Stack Copied to Java Heap ]                 [ Complete resource starvation ]
```

### Code Example: Pinning vs. Yielding
Below is a clean, demonstrative Java snippet showing how to trigger Carrier Thread yielding correctly, and how we inadvertently cause Carrier Thread pinning.

```java
import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.ReentrantLock;

public class CarrierMechanicsDemo {

    private static final ReentrantLock lock = new ReentrantLock();
    private static final Object monitor = new Object();

    public static void main(String[] args) throws InterruptedException {
        // We use a structured task scope or a simple executor to run our tasks
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            
            // Task 1: Good Citizen (Yields and unmounts properly)
            executor.submit(() -> {
                lock.lock();
                try {
                    System.out.println("VT 1: Mounted. About to block (will unmount safely)...");
                    // Thread.sleep in Loom is non-blocking to the carrier!
                    Thread.sleep(Duration.ofSeconds(1)); 
                    System.out.println("VT 1: Resumed and finishing.");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    lock.unlock();
                }
            });

            // Task 2: Bad Citizen (Pins the carrier thread!)
            executor.submit(() -> {
                // Synchronized block pins the virtual thread to its carrier!
                synchronized (monitor) {
                    try {
                        System.out.println("VT 2: Mounted. About to block inside synchronized block (PINNED!)...");
                        // This sleep blocks the actual Carrier Thread because of synchronized!
                        Thread.sleep(Duration.ofSeconds(1)); 
                        System.out.println("VT 2: Finished work.");
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }
            });
        }
    }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The JVM Internals: How Mounting Actually Happens
When a Virtual Thread transitions to the running state, the JVM executes a transition on the Carrier Thread. 

1. **Stack Copying**: The stack frames of a virtual thread are stored as Java objects on the **Heap**. When mounting, these frames are written into the physical execution stack of the carrier platform thread. 
2. **Continuation**: Virtual threads are built on top of **Continuations** (specifically `jdk.internal.vm.Continuation`). A continuation represents a block of code that can suspend its execution and resume later.
3. **The Scheduler**: The scheduler is a static, shared `ForkJoinPool` running in **FIFO (First-In-First-Out)** mode. Unlike the standard `ForkJoinPool.commonPool()` (used for parallel streams) which runs in LIFO mode to maximize CPU cache locality, Virtual Threads prioritize fairness and throughput across I/O tasks.

```text
       VIRTUAL THREAD (HEAP)                       CARRIER THREAD (NATIVE STACK)
 ┌────────────────────────────────┐                ┌────────────────────────────────┐
 │ Continuation Stack Object      │                │ Native Frame (Run loop)        │
 │  ├─ Method C() [state: paused] │  ══ Mount ══>  │  ├─ Method C() [Active]        │
 │  ├─ Method B()                 │                │  ├─ Method B()                 │
 │  └─ Method A()                 │                │  └─ Method A()                 │
 └────────────────────────────────┘                └────────────────────────────────┘
```

### The "Pinning" Trap
A Virtual Thread **cannot** yield (unmount) from its carrier if it is:
1. Executing inside a `synchronized` block or method.
2. Executing inside a native frame (e.g., JNI calls or Foreign Function interfaces).

When pinned, the Carrier Thread blocks along with the virtual thread. If your Carrier pool size is 16, and 16 virtual threads are pinned waiting on a database query within `synchronized` blocks, **your application is completely deadlocked** until those queries return.

#### How to detect and fix Pinning:
* **Detection**: Run your JVM with the VM option:
  `-Djdk.tracePinnedThreads=full` or `-Djdk.tracePinnedThreads=short`
  This will print a stack trace to standard error whenever a virtual thread pins its carrier.
* **Remediation**: Replace `synchronized` blocks with modern concurrency primitives like `ReentrantLock` or `StampedLock`.

---

### Interviewer Probe Questions

#### Probe 1: "If Virtual Threads use a `ForkJoinPool` under the hood, how does this scheduler avoid the thread exhaustion that typical thread pools suffer from?"
**Answer**: 
> "The scheduler itself doesn't avoid exhaustion; the *non-blocking runtime API* does. In a typical thread pool, if you call `socket.read()`, the platform thread sits idle inside the OS kernel queue, consuming 1MB of stack memory and OS scheduling overhead. 
> With Virtual Threads, the Java runtime rewrote almost all I/O operations (like `SocketChannel`, `FileChannel`, `Thread.sleep`) to yield the virtual thread's execution rather than blocking the thread. The virtual thread's stack is written to the heap, and the Carrier Thread is immediately returned to the `ForkJoinPool` to do other work. Thus, we only need as many Carrier Threads as there are physical CPU cores to schedule millions of tasks."

#### Probe 2: "What happens to `ThreadLocal` variables when a Virtual Thread unmounts? Do they leak into the next Virtual Thread running on that Carrier?"
**Answer**:
> "No, they do not leak. `ThreadLocal` variables are bound to the `VirtualThread` object itself, not to the underlying `CarrierThread`. 
> When a virtual thread unmounts, its thread locals remain on the heap inside the virtual thread's context. When the carrier thread picks up a new virtual thread, it reads the new virtual thread's local variables. 
> However, we must still be careful: because virtual threads are cheap and we spin up millions of them, using heavy objects in `ThreadLocal` variables can easily trigger OutOfMemoryErrors (OOM). We should favor **Scoped Values** (introduced in modern Java) to share read-only data safely."

#### Probe 3: "Why does replacing `synchronized` with `ReentrantLock` solve the pinning issue if both block execution?"
**Answer**:
> "Under the hood, `synchronized` is a JVM-level primitive that locks an object monitor tied tightly to the operating system thread execution state. The JVM's current implementation of Loom cannot decouple this association during a native monitor wait.
> Conversely, `ReentrantLock` is written in pure Java (built on top of `AbstractQueuedSynchronizer`). Since it's pure Java, when a virtual thread attempts to acquire a locked `ReentrantLock`, it parks using `LockSupport.park()`. The Virtual Thread API intercepts this call, gracefully unmounts the virtual thread, and saves its execution state to the heap without blocking the underlying Carrier Thread."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Carrier Threads are physical platform threads** managed by a private `ForkJoinPool` that execute the virtual threads. Virtual threads are simply execution states stored on the JVM heap.
2. **Mounting/Unmounting is fast** but not free. The JVM copies the stack frames of your execution from the heap to the OS stack and vice versa.
3. **Pinning is the ultimate enemy** of Project Loom. Running `synchronized` blocks or native code during long I/O operations locks the carrier thread, preventing scaling.

### 1 "Golden Rule" to remember
> *"Keep your synchronized blocks short, or swap them for `ReentrantLock`, and never perform heavy block-level I/O inside synchronized blocks if you want your Virtual Threads to fly."*