---
title: The Lock-Free Stack: Mastering CAS and Lock-Free Custom Collections
date: 2026-06-17T04:46:41.008184
---

# The Lock-Free Stack: Mastering CAS and Lock-Free Custom Collections

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
A **Lock-Free Stack** (often called a **Treiber Stack**) is a thread-safe, Last-In-First-Out (LIFO) collection that allows multiple threads to push and pop items simultaneously *without ever locking*. Instead of making threads wait in line (blocking), it uses a clever "try-and-retry" strategy powered by raw CPU hardware instructions.

### A Real-World Analogy
Imagine a physical **receipt spindle** on a restaurant kitchen counter where the chef impales orders. 

```
   [Spindle]
      ||
      || <-- (Chef tries to drop a ticket here)
   ======
```

*   **The Locked Approach:** Only one cook is allowed near the spindle at a time. A security guard blocks all other cooks. If the cook at the spindle takes their time, everyone else idly stands around wasting time.
*   **The Lock-Free (CAS) Approach:** Multiple cooks can walk up to the spindle at once. A cook looks at the top ticket, writes their new ticket, and tries to impale it. If another cook sneaks a ticket on top *one millisecond* before them, the first cook doesn't go to sleep or wait; they simply look at the *new* top ticket, adjust their target, and try again instantly. 

Nobody ever blocks or sleeps; they just loop until they succeed.

### Why should I care?
In traditional multithreading, we use locks (`synchronized` or `ReentrantLock`). When a thread hits a lock held by another thread, the Operating System **suspends** it (a Context Switch). 

Context switches are incredibly expensive—they require saving CPU registers, flushing caches, and reloading thread states. A Lock-Free Stack solves this by keeping threads running at 100% CPU efficiency, eliminating the overhead of OS-level thread blocking. It is the backbone of high-throughput, low-latency architectures.

---

## 2. 🛠️ How it Works (Step-by-Step)

The magic behind lock-free structures is an atomic CPU operation called **Compare-And-Swap (CAS)**. 

Instead of saying *"Set this value to X"*, a thread says: *"I expect the current value to be `A`. If it is still `A`, change it to `B`. If it is not `A`, do nothing and tell me I failed."*

### Step-by-Step Flow: The `push` Operation
1.  **Read:** Read the current `head` of the stack.
2.  **Prepare:** Create a new node pointing to this current `head`.
3.  **Commit (CAS):** Attempt to swap the `head` pointer from the old head to your new node.
    *   *If success:* The push is complete!
    *   *If failure:* (Another thread modified the head in the meantime), discard the change, read the new head, and try again.

### The ASCII Flow

```
Thread A wants to push Node(30) to a stack of [20 -> 10]:

Step 1: Read Head                     Step 2: Create New Node
   Head ---> [20] -> [10]                [30] ---> [20] -> [10]
              ^
              | (Thread A expects this)

Step 3: Atomic CAS (Compare-and-Swap)
   If Head is still [20], swap Head to point to [30].
   
   SUCCESS:                             FAILURE (Another thread pushed [40] first):
   Head ---> [30] -> [20] -> [10]       Head has changed to [40]!
                                        Thread A must retry with [30] pointing to [40].
```

### Code Implementation (Java)

Here is a clean, production-grade custom implementation of a lock-free Treiber Stack:

```java
import java.util.concurrent.atomic.AtomicReference;

public class LockFreeStack<T> {

    // AtomicReference acts as our memory-barrier-protected "head" pointer
    private final AtomicReference<Node<T>> head = new AtomicReference<>(null);

    // Node structure: immutable data, mutable next pointer
    private static class Node<T> {
        final T value;
        Node<T> next;

        Node(T value) {
            this.value = value;
        }
    }

    /**
     * Pushes an item onto the top of the stack.
     * Non-blocking, lock-free, thread-safe.
     */
    public void push(T value) {
        if (value == null) throw new NullPointerException("Null values not allowed");
        Node<T> newHead = new Node<>(value);
        Node<T> currentHead;

        do {
            // Step 1: Read the current state of the head
            currentHead = head.get();
            // Step 2: Tentatively link our new node to the current head
            newHead.next = currentHead;
            
            // Step 3: CAS. Attempt to atomically set head to newHead IF head is still currentHead.
            // If head was changed by another thread, head.get() != currentHead, CAS returns false, loop retries.
        } while (!head.compareAndSet(currentHead, newHead));
    }

    /**
     * Pops an item from the top of the stack.
     * Returns null if the stack is empty.
     */
    public T pop() {
        Node<T> currentHead;
        Node<T> newHead;

        do {
            // Step 1: Read the current head
            currentHead = head.get();
            if (currentHead == null) {
                return null; // Stack is empty
            }
            // Step 2: Identify what the new head should be
            newHead = currentHead.next;

            // Step 3: CAS. Attempt to transition from currentHead to newHead
        } while (!head.compareAndSet(currentHead, newHead));

        // Return the value of the successfully popped node
        return currentHead.value;
    }

    /**
     * Helper to check if the stack is currently empty.
     */
    public boolean isEmpty() {
        return head.get() == null;
    }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Hardware & JVM Internals
How does `compareAndSet` avoid locking? Under the hood, the JVM translates `compareAndSet` to highly specific CPU instructions. On x86 architectures, it compiles down to the assembly instruction:

```assembly
LOCK CMPXCHG <destination>, <source>
```

The `LOCK` prefix tells the CPU to assert the memory bus lock (or use cache coherency protocols like MESI) to make the comparison and swap happen as an **indivisible, atomic hardware operation**. No operating system scheduler is involved, meaning zero thread-suspension overhead.

### Lock-Free vs. Wait-Free
*   **Lock-Free:** Guarantees that *at least one* thread makes progress in any given step. If 10 threads attempt to push at once, 1 will succeed immediately, and 9 will retry. The system as a whole never freezes, but individual threads can theoretically spin forever under extreme contention.
*   **Wait-Free:** A stronger guarantee. *Every* thread is guaranteed to complete its operation in a finite number of steps (e.g., `AtomicInteger.get()`). Treiber's Stack is **Lock-Free**, not Wait-Free, because of the retry loop.

### The Trade-offs

| Factor | Lock-Based Stack (`Collections.synchronizedList`) | Lock-Free Stack (Treiber Stack) |
| :--- | :--- | :--- |
| **Low Contention Speed** | Moderate | **Blazing Fast** (Zero OS overhead) |
| **High Contention Behavior**| Threads block (CPU consumption drops, but latency spikes) | Threads spin (High CPU consumption, but overall throughput remains high) |
| **Memory Allocation** | Low (Can use reusable array backing) | High (Requires a new wrapper `Node` object for every push) |

### The Infamous "ABA Problem"
The ABA problem is the most common trap when implementing custom lock-free collections.

#### Scenario:
1. Thread 1 reads `head` which has value `A`.
2. Thread 1 gets preempted (paused).
3. Thread 2 pops `A`, pops `B`, and then pushes `A` back onto the stack.
4. Thread 1 wakes up, checks if `head` is still `A`. Since it is `A`, Thread 1 completes the CAS successfully.

```
Initial Stack: [A] -> [B] -> [C]
Thread 1 reads A, intends to swap head to B.
Thread 2 alters stack:
   Pop A  -> Stack is [B] -> [C]
   Pop B  -> Stack is [C]
   Push A' -> Stack is [A'] -> [C]  (Note: B is completely gone!)
Thread 1 performs CAS(Expected: A, New: B).
CRASH: Thread 1 sets Head to B, but B was already deleted/freed!
```

#### Why doesn't our Java implementation suffer from this?
Java uses **automatic garbage collection**. In Java, when Thread 2 pops `B`, the node containing `B` cannot be recycled or reallocated to represent a new value as long as Thread 1 still holds an active reference to it (`newHead = currentHead.next`). 

In non-garbage-collected languages like C/C++, this exact scenario results in severe memory corruption. To solve the ABA problem in C++ or when reusing nodes in Java, we must use **Epoch-based reclamation**, **Hazard Pointers**, or versioned references (like `AtomicStampedReference`).

---

### Interviewer Probe Questions

#### 1. "If lock-free structures are so fast, why isn't the entire Java Collections Framework lock-free?"
**Answer:** Lock-free structures are highly specialized and come with structural costs. 
*   They are susceptible to **high CPU utilization under extreme write contention** (because threads spin-retry). 
*   They cannot easily support operations that span multiple nodes atomically (like `size()` or `addAll()`) without massive performance penalties.
*   They usually require object allocation for node wrappers, causing GC pressure. Lock-based array structures are often more space-efficient.

#### 2. "How would you implement a lock-free `size()` method for this stack?"
**Answer:** In lock-free design, getting an *exact* size is notoriously difficult. If you traverse the nodes to count them, the stack could change while you are traversing. 

There are two approaches:
1.  **Weakly Consistent:** Walk the stack and count. Accept that the value may be obsolete the moment it is returned.
2.  **Tracking Counter:** Keep an `AtomicInteger size` counter. Increment it on successful `push` and decrement on successful `pop`. Under high contention, this creates a **hotspot**—every thread will now fight over the `size` counter CAS *and* the `head` pointer CAS, which severely limits scalability. (A better high-performance compromise is using a `LongAdder`).

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1.  **Zero Blocking:** Lock-free collections use CPU-level hardware optimization (`CAS`) to ensure threads never transition to the OS `BLOCKED` state.
2.  **Optimistic Concurrency:** Instead of securing a lock beforehand, threads assume no conflict will occur, perform the work, and check for conflicts at the very last millisecond.
3.  **Garbage Collector Dependent:** The classic Treiber Stack relies heavily on JVM Garbage Collection to naturally neutralize the dangerous **ABA problem**.

### 🌟 The Golden Rule
> Use **Lock-Free Collections** when write contention is low-to-medium and latency requirements are strict. If write contention is extremely high and sustained, prefer **Lock-Based** collections to prevent threads from consuming 100% CPU spinning in retry loops.