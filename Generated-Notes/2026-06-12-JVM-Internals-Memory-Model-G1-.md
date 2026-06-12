---
title: JVM Concurrency Barriers: G1's SATB Write Barrier vs. ZGC's Self-Healing Load Barrier
date: 2026-06-12T04:46:37.187419
---

# JVM Concurrency Barriers: G1's SATB Write Barrier vs. ZGC's Self-Healing Load Barrier

---

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
When a Garbage Collector (GC) runs concurrently, it cleans up memory *while your application is actively running*. 

Think of your running application threads (called **Mutators**) as kids playing with toys, and the **Garbage Collector** as a parent trying to clean up the room. If the kids keep moving toys from the "keep" pile to the "throw away" pile while the parent is sweeping, the parent might accidentally throw away a toy that is still being played with.

To prevent this, the JVM uses **GC Barriers**. These are not hardware memory barriers (like `volatile`), but rather tiny, stealthy pieces of code that the JIT compiler injects into your application's read and write operations. They act as "traffic cops" to make sure the GC and your application stay in perfect sync.

### The Real-World Analogy
Imagine a massive library where books are constantly being moved:
*   **G1 GC (Write Barrier / SATB):** The librarian takes a physical snapshot of the shelves at 9:00 AM (**Snapshot-At-The-Beginning**). If a visitor (your app) wants to put a book back or move it to a different shelf, they must first log the book's *original* location in a notebook. The librarian checks this notebook later to make sure no books were lost in transit.
*   **ZGC (Load Barrier / Self-Healing):** Instead of logging moves, the librarian places a smart security tag on every book. When a visitor reaches out and *touches* a book (a Load operation), the tag instantly checks if the book needs to be repaired or moved to a new wing. If it does, the visitor's hand is paused for a microsecond while the tag "heals" the book’s location. From then on, everyone accesses the correct spot instantly.

### Why should I care?
If you configure your JVM poorly, these barriers can introduce silent overhead. Understanding how **G1 (Garbage-First)** and **ZGC (Z Garbage Collector)** track live objects allows you to make informed decisions between high-throughput workloads (G1) and ultra-low-latency APIs (ZGC), saving your system from catastrophic Stop-The-World (STW) pauses.

---

## 2. 🛠️ How it Works (Step-by-Step)

To understand barriers, we must first understand the **Tri-color Abstraction** used by GCs to mark live objects:
*   ⚪ **White:** Unvisited objects (candidates for GC deletion).
*   🔘 **Grey:** The object itself is visited, but its fields (referenced objects) haven't been scanned yet.
*   ⚫ **Black:** The object and all its immediate references have been fully scanned.

The ultimate danger in concurrent GC is when the application thread does two things simultaneously:
1. Disconnects a White object from a Grey object.
2. Attaches that same White object to a Black object.

Since the GC never rescans Black objects, that White object becomes "invisible" and will be accidentally deleted!

```
[Black Object] --------(Mutator adds link)--------> [White Object] (Accidentally Swept!)
      |                                                    ^
      |                                                    |
[Grey Object]  xxxxxxx(Mutator breaks link)xxxxxxxxxxxxxxxx|
```

---

### Step-by-Step: How G1 GC Prevents This (Write Barrier - SATB)

G1 uses a **Pre-Write Barrier** to preserve the "Snapshot-At-The-Beginning".

```
[App Thread] ---> Modifies reference (obj.field = newRef)
                       |
                       v
             [G1 Pre-Write Barrier]
                       |
             Is GC marking active?
                 /          \
             (Yes)          (No) ---> Run normal CPU write instruction
               /
     Read *old* value of obj.field
               |
  Push old value to Thread-Local SATB Buffer
               |
  (Buffer Full?) ---> Hand off to GC Refinement Thread (Mark it Grey)
```

1. **Interception:** Before your code executes `x.field = y`, G1 intercepts the write.
2. **Capture:** It reads the *old* value that was stored in `x.field`.
3. **Queueing:** It pushes this old value into a thread-local SATB buffer. 
4. **Processing:** When the buffer fills up, it's handed over to concurrent GC threads to be marked as Grey, ensuring it won't be collected in this cycle.

---

### Step-by-Step: How ZGC Prevents This (Load Barrier)

ZGC doesn't care about writes. It intercepts **Reads** (Loads) using **Colored Pointers** (metadata bits embedded directly inside the 64-bit object reference).

```
[App Thread] ---> Reads reference (var x = obj.field)
                       |
                       v
              [ZGC Load Barrier]
                       |
         Does reference bit match GC phase? 
         (e.g., Is "Marked" bit correct?)
                 /          \
             (Yes)          (No) ---> [Slow Path Triggered]
               /                            |
       [Fast Path]                 Relocate/Remap Object
   Return pointer immediately               |
                             Update (Self-Heal) obj.field with new address
                                            |
                                   Return new pointer
```

1. **Dereference:** Your application attempts to read a field: `Object local = person.address`.
2. **Metadata Test:** The JIT-compiled load barrier executes a fast, single-digit assembly test checking the color bits of the pointer.
3. **The Slow Path (Remap/Relocate):** If the pointer's color indicates it hasn't been processed yet, the thread takes a minor detour (the slow path). It relocates the object if the GC is in a relocating phase, or marks it.
4. **Self-Healing:** The barrier updates the reference inside `person.address` directly on the heap to point to the new, corrected location. Subsequent reads will hit the fast path.

### Code Demonstration: What the JIT Compiler Actually Generates

Here is a conceptual Java representation of what the JIT compiler emits behind the scenes for both G1 and ZGC.

```java
public class BarrierDemo {
    private Object field;

    // --- G1 WRITE BARRIER DEMO ---
    public void updateFieldG1(Object newValue) {
        // Conceptual JIT-generated code for G1 Write Barrier:
        Object oldValue = this.field; 
        if (G1GC_IsMarkingActive()) {
            if (oldValue != null) {
                enqueueSATBBuffer(oldValue); // Prevent GC from losing track of oldValue
            }
        }
        this.field = newValue; // The actual write operation
    }

    // --- ZGC LOAD BARRIER DEMO ---
    public Object readFieldZGC() {
        // Conceptual JIT-generated code for ZGC Load Barrier:
        Object ptr = this.field;
        if (isBadColorPointer(ptr)) { // Fast-path bitwise check
            ptr = resolveBadPointerSlowPath(this, ptr); // Resolves, relocates, and self-heals
        }
        return ptr; // The actual read operation (guaranteed to be correct)
    }

    private static native boolean G1GC_IsMarkingActive();
    private static native void enqueueSATBBuffer(Object val);
    private static native boolean isBadColorPointer(Object ptr);
    private static native Object resolveBadPointerSlowPath(Object holder, Object badPtr);
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Deep Technical Magic

#### G1's SATB (Snapshot-At-The-Beginning)
SATB is based on the assumption that any object that was alive at the *start* of the GC cycle, or allocated *during* the cycle, is considered live. 
*   **The Trap:** It can create **Floating Garbage** (objects that died during the cycle but are kept alive because they were caught in the snapshot).
*   **The Benefit:** Extremely low marking overhead because the GC doesn't need to recursively scan newly mutated references dynamically.

#### ZGC's Colored Pointers & Virtual Memory Multi-mapping
ZGC uses the top bits of a 64-bit reference pointer to store state metadata:

```
+-------------------+-+----+-----------------------------------------------+
| 16 bits (unused)  |1|4   |               43 bits                         |
|                   |v|bits|               Object Address                  |
+-------------------+-+----+-----------------------------------------------+
                     |  |
                     |  +---> Metadata (Marked0, Marked1, Remapped)
                     +------> Finalizable Bit
```

Because these metadata bits are part of the pointer, referencing them directly would crash the OS with a segmentation fault. To bypass this, ZGC uses **Virtual Memory Multi-mapping**. The JVM maps three different virtual address spaces (corresponding to different color bit combinations) to the *same* physical memory address space. 

To the OS, they look like different addresses; to the hardware, they point to the exact same physical RAM.

---

### Trade-offs

| Feature | G1 GC (Write Barriers) | ZGC (Load Barriers) |
| :--- | :--- | :--- |
| **Primary Goal** | High throughput with predictable pauses. | Ultra-low latency (pauses < 1ms) regardless of heap size. |
| **Barrier Overhead** | Paid during **Writes**. Write-heavy applications (e.g., massive cache engines) suffer a slight CPU penalty. | Paid during **Reads**. Read-heavy applications suffer a minor instruction-cache penalty. |
| **Memory Overhead** | High. Requires Card Tables and Remembered Sets (RSet) to track inter-region references. | Low. No RSets are needed, but requires a 64-bit virtual memory address space. |
| **Floating Garbage** | Higher, due to SATB strictness. | Lower, because of precise concurrent relocation. |

---

### Interviewer Probes (Tricky Questions & Winning Answers)

#### Probe 1: "Since ZGC uses load barriers on every single read, why doesn't it completely destroy application throughput?"
*   **The Trap:** The interviewer expects you to say "it does," or to struggle to explain why it's fast.
*   **Winning Answer:** "The ZGC load barrier is highly optimized by the JIT compiler. The 'fast path' is inlined as a simple bit-test instruction (`test` or `and` at the assembly level) on the pointer itself, which takes less than a nanosecond and matches CPU branch predictors perfectly. The expensive 'slow path' (relocation and self-healing) is only executed once per unique object pointer per GC cycle. Once a reference is 'self-healed' on the heap, subsequent reads bypass the slow path entirely."

#### Probe 2: "What is the difference between G1's pre-write barrier and post-write barrier?"
*   **The Trap:** Forgetting that G1 uses *two* barriers for writes.
*   **Winning Answer:** "G1 uses two distinct barriers for writes:
    1.  The **Pre-Write Barrier (SATB)**: Executed *before* a reference mutation. It captures the *old* value to ensure concurrent marking doesn't miss reachable objects.
    2.  The **Post-Write Barrier**: Executed *after* a reference mutation. It logs the write in G1's **Card Table** (marking the corresponding memory cards as dirty). This allows G1 to track cross-region references without scanning the entire heap during minor collections."

#### Probe 3: "Why can't ZGC run on 32-bit operating systems or with Compressed OOPs enabled?"
*   **The Trap:** Testing your fundamental understanding of hardware limits and pointer representation.
*   **Winning Answer:** "ZGC relies fundamentally on **Colored Pointers**, which require metadata bits to be embedded directly within the reference address. A 32-bit JVM only has 4GB of addressable space, leaving no spare bits for GC metadata. Similarly, **Compressed OOPs** (Compressed Ordinary Object Pointers) compress 64-bit references into 32-bit relative offsets, stripping out the metadata bits required by ZGC's load barrier mechanism. Therefore, ZGC enforces 64-bit uncompressed addresses."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1.  **G1 is Write-Heavy:** It intercept writes to keep an immutable snapshot (SATB) of the heap. This protects throughput but allows some temporary "floating garbage".
2.  **ZGC is Read-Heavy:** It intercepts reads using colored pointers. It fixes broken references on-the-fly ("Self-Healing"), keeping pause times under 1 millisecond even on terabyte heaps.
3.  **Barriers are JIT-Injected:** They are not OS-level locks; they are assembly instructions injected by the JIT compiler directly into your application's execution path.

### 1 "Golden Rule"
> **Choose G1 when your hardware is CPU-constrained and you can tolerate 100ms pauses for max throughput; choose ZGC when SLA latency consistency (under 1ms) is your absolute, non-negotiable metric.**