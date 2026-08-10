---
title: CompletableFuture Lock-Free State Machine: Treiber Stacks, Completion Chains, and AltResult Mechanics
date: 2026-08-10T04:47:05.280372
---

# CompletableFuture Lock-Free State Machine: Treiber Stacks, Completion Chains, and AltResult Mechanics

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
When you chain operations on a `CompletableFuture`—such as `.thenApply()`, `.thenAccept()`, or `.exceptionally()`—Java does not execute them immediately if the preceding result isn't ready. Instead, it builds an **internal state machine**. 

Dependent tasks are pushed onto a lock-free, single-linked stack inside the `CompletableFuture` object. Once the main computation finishes, Java unwinds this stack and runs or dispatches every dependent stage without using heavyweight OS locks.

---

### Real-World Analogy: The Airport Customer Desk
Imagine an airport customer service desk:
* **The Agent (The Main Task):** Currently rebooking a flight.
* **Passengers (Dependent Tasks):** Need boarding passes or baggage tags, but the agent isn't finished yet.
* **The Sticky-Note Stack (The Treiber Stack):** Instead of waiting in a blocking physical line that halts traffic, each passenger leaves a sticky note on a spike on the agent's desk. Each new sticky note is placed on top of the last one.
* **The Completion Event:** The agent finishes the flight rebooking. They take the stack of sticky notes from top to bottom and execute each request immediately.
* **The Red Alert Box (`AltResult`):** If the system crashes, the agent places a red alert card on the desk. Every passenger coming to check the desk immediately knows the process failed without waiting for individual attempts.

---

### Why should I care?
1. **Zero Lock Overhead:** `CompletableFuture` scales across thousands of concurrent operations because it uses atomic Compare-And-Swap (CAS) instructions instead of `synchronized` locks.
2. **Prevent Silent Failures:** Understanding how exceptions are stored internally prevents bugs where exceptions disappear into unhandled async stages.
3. **Avoid Memory Leaks:** Knowing how completion stages hold references to one another prevents subtle memory bloat in long-lived asynchronous pipelines.

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Execution Process
1. **Creation (`result == null`):** A `CompletableFuture` is instantiated. Both its internal `result` field and its dependent stage `stack` pointer are `null`.
2. **Dependency Attachment (Treiber Stack Push):** Calling a dependent method (e.g., `.thenApply()`) before completion creates a `Completion` object. The JVM uses a lock-free CAS loop (`VarHandle`) to push this node onto the top of the `stack`.
3. **Completion Transition:**
   * **Success:** `result` is set to the returned value using a CAS operation. If the returned value is `null`, Java sets `result` to an internal sentinel object called `NIL`.
   * **Failure:** If an exception is thrown, Java wraps the `Throwable` inside an internal `AltResult` object and CAS-assigns it to `result`.
4. **Stack Unwinding (`postComplete`):** The thread that transitions `result` from `null` to non-null takes ownership of the `stack`. It pops nodes off the lock-free Treiber stack one by one and executes them (or offloads them to an `Executor` if `*Async` variants were used).

---

### Visual Representation

```
   BEFORE COMPLETION (Adding Dependent Stages):
   ============================================
   
   CompletableFuture Object
   +---------------------------------------+
   | result: null                          |
   | stack:  [Stage C] -> [Stage B] -> [Stage A] -> null
   +---------------------------------------+
                ^
                | (CAS Push via Treiber Stack)
          .thenApply(...)

   --------------------------------------------------------

   AFTER COMPLETION (Result Set & Unwinding Stack):
   ===============================================

   CompletableFuture Object
   +---------------------------------------+
   | result: AltResult(Throwable) OR Value |
   | stack:  null (Claimed by Completer)   |
   +---------------------------------------+
                |
                v  Unwinds Top-to-Bottom
           [Stage C] ---> [Stage B] ---> [Stage A]
```

---

### Code Demonstration

```java
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;

public class CompletableFutureInternalsDemo {

    public static void main(String[] args) throws InterruptedException, ExecutionException {
        // Step 1: Instantiate uncompleted future (result == null, stack == null)
        CompletableFuture<String> stringFuture = new CompletableFuture<>();

        // Step 2: Attach multiple dependent stages prior to completion
        // These get pushed onto stringFuture's lock-free Treiber stack
        CompletableFuture<Integer> lengthFuture = stringFuture
            .thenApply(val -> {
                System.out.println("[Thread: " + Thread.currentThread().getName() + "] Stage 1: Transforming string to length");
                return val.length();
            });

        CompletableFuture<Boolean> isEvenFuture = lengthFuture
            .thenApply(len -> {
                System.out.println("[Thread: " + Thread.currentThread().getName() + "] Stage 2: Checking if length is even");
                return len % 2 == 0;
            });

        System.out.println("Pipeline defined. Main thread triggering completion...");

        // Step 3: Complete the root future
        // Whichever thread executes complete() claims the Treiber stack and unwinds it directly inline
        // unless an async executor was specified.
        stringFuture.complete("VirtualThreadsAndCompletableFuture");

        // Step 4: Verify outputs
        System.out.println("Result of isEvenFuture: " + isEvenFuture.get());
    }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### How Java Implements This Under the Hood

#### 1. The Atomic Storage Engine
Inside `java.util.concurrent.CompletableFuture`, memory updates are controlled via `VarHandle` (or `Unsafe` in older Java versions):

```java
// Simplified snippet of actual JDK source structure
public class CompletableFuture<T> implements Future<T>, CompletionStage<T> {
    volatile Object result;       // Holds result T, NIL, or AltResult
    volatile Completion stack;    // Top of lock-free Treiber stack

    // VarHandle mechanics for CAS operations
    private static final VarHandle RESULT;
    private static final VarHandle STACK;
}
```

#### 2. The `AltResult` Pattern
Because `volatile Object result` uses `null` to mean **"not completed yet"**, `CompletableFuture` cannot store a literal `null` return value directly in `result`.

To overcome this, the JVM uses internal wrappers:
* **Literal `null` return:** Represented by a static sentinel `AltResult NIL = new AltResult(null)`.
* **Exceptions:** Represented by `AltResult(Throwable ex)`.
* **Value return:** Stored directly as the raw object reference.

When you call `.get()` or `.join()`, the JVM inspects `result`:
```java
// Internal concept of result extraction
Object r = this.result;
if (r instanceof AltResult) {
    Throwable x = ((AltResult)r).ex;
    if (x == null) return null; // It was NIL
    throw new CompletionException(x); // Wrap and rethrow
}
return (T) r; // Direct typed return
```

---

#### 3. The Treiber Stack Mechanism
When multiple threads attach stages to the same pending `CompletableFuture` at the same time, no thread locks. Instead, they run a **lock-free Treiber Stack CAS loop**:

```java
// Concept of push logic inside CompletableFuture
final void pushStack(Completion c) {
    do {
        c.next = stack;
    } while (!STACK.compareAndSet(this, c.next, c)); // Atomically update top of stack
}
```

When `complete(v)` is invoked:
1. `RESULT.compareAndSet(this, null, encodeValue(v))` attempts to transition `result` from `null`.
2. If successful, the thread calls `postComplete()`, which executes a `STACK.getAndSet(this, null)` to atomically claim the **entire linked stack of dependent tasks**.
3. It iterates through the chain, calling `tryFire()` on each node.

---

### Trade-offs & Behavioral Edge Cases

| Attribute | Mechanism | Impact / Trade-off |
| :--- | :--- | :--- |
| **Execution Memory Overhead** | Treiber Stack nodes (`UniApply`, `BiApply`, etc.) allocation on heap. | Extremely low GC overhead compared to OS threads, but long un-completed stage chains consume heap space. |
| **Stack Depth / Recursion** | Synchronous `.thenApply()` chains unwind synchronously on completing thread. | Deep synchronous chains (e.g., 10,000 recursive completions) can trigger a `StackOverflowError`. Use `*Async` variants to break execution stacks. |
| **Contention Model** | Lock-Free CAS loops (`VarHandle`). | Zero thread blocking when building execution pipelines; minor CPU spinning under extreme concurrent stage attachment. |

---

### Interviewer Probes (Tricky Questions & Answers)

#### Probe 1: "How does `CompletableFuture` handle returning a `null` value vs. being uncompleted, since both seem to involve `null`?"
* **Answer:** `CompletableFuture` uses `null` strictly to indicate that the future is **uncompleted**. If a task completes successfully with a `null` return value, the JVM internally assigns an `AltResult` wrapper with a `null` exception field (often referenced as static sentinel `NIL`). This cleanly separates state representation from output values.

#### Probe 2: "If Thread A completes a `CompletableFuture` while Threads B and C are calling `.thenApply()` on it simultaneously, how does `CompletableFuture` guarantee no tasks are missed or executed twice without using locks?"
* **Answer:** It uses atomic CAS state transitions via `VarHandle`:
  1. Threads B and C use a CAS loop to attempt pushing their `Completion` nodes onto `stack`.
  2. Thread A uses a CAS instruction to transition `result` from `null` to its final value.
  3. Once `result` is non-null, any subsequent call to `.thenApply()` detects that `result` is already set; instead of pushing to the stack, it executes the callback immediately on the caller's thread.
  4. Meanwhile, Thread A atomically claims whatever was on the stack at the moment of completion using `STACK.getAndSet(this, null)` and processes those nodes.

#### Probe 3: "Why can chaining thousands of synchronous stages in `CompletableFuture` throw a `StackOverflowError`, and how do you prevent it?"
* **Answer:** When a `CompletableFuture` completes, `postComplete()` unwinds and fires dependent stages synchronously inline on the completing thread. If stage $A$ completes stage $B$, which completes stage $C$, each call stays on the call stack. Deep, non-async completion chains build up OS stack frames. To prevent this, use `thenApplyAsync()` or `thenComposeAsync()`, which hands off execution to an `Executor` (or Virtual Thread), resetting the call stack frame.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **State Storage:** `CompletableFuture` uses a single `volatile Object result` field to store the state (uncompleted = `null`, success = value or `NIL`, failure = `AltResult`).
2. **Treiber Stack Push:** Uncompleted futures store dependent callbacks in a lock-free, CAS-driven linked stack.
3. **Execution Ownership:** The thread that successfully sets `result` via CAS "wins" ownership of the Treiber stack, clears it, and fires all callbacks.

---

### 1 Golden Rule
> **If your async pipeline involves recursive or deep stage chaining, use `*Async` stage variants (e.g., `thenApplyAsync`) to offload work to a thread pool and avoid call-stack exhaustion.**