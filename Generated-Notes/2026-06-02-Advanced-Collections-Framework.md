---
title: The Bidirectional Map (BiMap): Custom Double-Indexed Associative Collections
date: 2026-06-02T04:46:52.053332
---

# The Bidirectional Map (BiMap): Custom Double-Indexed Associative Collections

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
A standard Map (like a `HashMap`) is a one-way street. You give it a **Key**, and it instantly hands you the **Value**. But if you have a Value and need to find its corresponding Key, a standard Map forces you to walk through every single entry one-by-one until you find a match. 

A **BiMap (Bidirectional Map)** is a two-way street. It enforces a strict **one-to-one (bijection)** relationship between Keys and Values. This allows you to look up a Value from a Key in $O(1)$ time, *and* look up a Key from a Value in $O(1)$ time.

```
Standard Map:   Key   ───(Fast O(1))───> Value
                Key   <──(Slow O(N))───  Value

BiMap:          Key   ───(Fast O(1))───> Value
                Key   <──(Fast O(1))───  Value
```

### Real-World Analogy
Think of a **Hotel Room Keycard System**.
* Every **Room Number** (Key) is mapped to exactly one active **Keycard ID** (Value).
* If a guest asks, *"Which keycard opens Room 302?"*, the receptionist looks up the Room Number to find the Keycard ID.
* If a keycard is found on the floor, the receptionist scans the Keycard ID to instantly look up which Room Number it belongs to.
* If you assign Room 302's keycard to Room 105, Room 302 immediately loses its access. There can never be two rooms assigned to the same card, or two cards assigned to the same room.

### Why should I care? What problem does it solve for me today?
Without a BiMap, developers who need two-way lookups usually do one of two bad things:
1. **Loop through the entire map:** Writing a `for` loop to scan values. This turns an $O(1)$ operation into an $O(N)$ operation, destroying performance as the collection grows.
2. **Manually maintain two separate Maps:** Keeping a `forwardMap<K, V>` and a `reverseMap<V, K>`. This is highly error-prone. If you update one map but forget to update or clean up the other, your data becomes corrupted, leading to silent, hard-to-debug state inconsistencies.

---

## 2. 🛠️ How it Works (Step-by-Step)

To build an efficient, custom BiMap, we maintain **two internal Maps** pointing in opposite directions. The secret sauce is maintaining the **bijection invariant**: if the mapping `A -> B` exists, then no other key can map to `B`, and `A` cannot map to any other value.

### The Lifecycle of a BiMap Write Operation
1. **Check for Key Collision:** If the key already exists, we must remove its old value from the reverse map.
2. **Check for Value Collision:** If the value already exists under a *different* key, we must throw an exception (or forcefully evict the old key-value pair if using a "force-put" strategy) to preserve the unique 1-to-1 relationship.
3. **Double Write:** Insert the mappings into both internal maps simultaneously.

### The Architecture Flow
```
    [ Put Operation: put(Key, Value) ]
                   │
         Does Key already exist?
          ├── Yes ──> Remove old Value from Reverse Map
          └── No ───> Continue
                   │
        Does Value already exist?
          ├── Yes ──> Reject (or Evict Old Key)
          └── No ───> Continue
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
[ Insert Forward ]            [ Insert Reverse ]
(forwardMap: K -> V)          (reverseMap: V -> K)
```

### The Code Implementation (Java)

Here is a clean, robust, custom implementation of a `BiMap`. It includes the standard `put` (which guards against duplicates) and a `forcePut` (which evicts conflicting entries).

```java
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public class CustomBiMap<K, V> {
    private final Map<K, V> forwardMap = new HashMap<>();
    private final Map<V, K> reverseMap = new HashMap<>();
    private final CustomBiMap<V, K> inverseView;

    // Package-private constructor for creating the live inverse view
    private CustomBiMap(Map<V, K> reverseMap, Map<K, V> forwardMap, CustomBiMap<V, K> inverseView) {
        this.forwardMap.putAll(forwardMap);
        this.reverseMap.putAll(reverseMap);
        this.inverseView = inverseView;
    }

    public CustomBiMap() {
        this.inverseView = new CustomBiMap<>(this.reverseMap, this.forwardMap, this);
    }

    /**
     * Puts a key-value pair into the BiMap.
     * Throws IllegalArgumentException if the value is already present in the map.
     */
    public V put(K key, V value) {
        Objects.requireNonNull(key, "Key cannot be null");
        Objects.requireNonNull(value, "Value cannot be null");

        if (forwardMap.containsKey(key) && Objects.equals(forwardMap.get(key), value)) {
            return value; // No change needed
        }

        if (reverseMap.containsKey(value)) {
            throw new IllegalArgumentException("Value already associated with another key: " + value);
        }

        // Remove old associations to prevent leaks
        if (forwardMap.containsKey(key)) {
            V oldValue = forwardMap.remove(key);
            reverseMap.remove(oldValue);
        }

        forwardMap.put(key, value);
        reverseMap.put(value, key);
        return null;
    }

    /**
     * Puts a key-value pair, silently evicting any existing key or value associations.
     */
    public void forcePut(K key, V value) {
        Objects.requireNonNull(key, "Key cannot be null");
        Objects.requireNonNull(value, "Value cannot be null");

        if (forwardMap.containsKey(key)) {
            V oldValue = forwardMap.get(key);
            if (Objects.equals(oldValue, value)) return;
            reverseMap.remove(oldValue);
        }

        if (reverseMap.containsKey(value)) {
            K oldKey = reverseMap.remove(value);
            forwardMap.remove(oldKey);
        }

        forwardMap.put(key, value);
        reverseMap.put(value, key);
    }

    public V get(K key) {
        return forwardMap.get(key);
    }

    public K getKey(V value) {
        return reverseMap.get(value);
    }

    public V remove(K key) {
        if (forwardMap.containsKey(key)) {
            V value = forwardMap.remove(key);
            reverseMap.remove(value);
            return value;
        }
        return null;
    }

    public int size() {
        return forwardMap.size();
    }

    public void clear() {
        forwardMap.clear();
        reverseMap.clear();
    }

    /**
     * Returns a live view of the inverse BiMap. 
     * Mutations on the inverse view reflect back into the original map.
     */
    public CustomBiMap<V, K> inverse() {
        return this.inverseView;
    }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical "Magic" & Memory Trade-offs
Under the hood, a BiMap trades **spatial complexity** for **temporal efficiency**. 
* **Time Complexity:** Every query (`get` and `getKey`) is $O(1)$ amortized. 
* **Space Complexity:** $O(N)$. Because we store two references for every mapping (one in `forwardMap`, one in `reverseMap`), the memory footprint is exactly double that of a standard `HashMap`.

```
[ Heap Memory Allocation ]
  ┌──────────────────────────────────────────────────┐
  │  forwardMap Entry: [Hash(Key) -> Node(Key, Val)]  │
  │  reverseMap Entry: [Hash(Val) -> Node(Val, Key)]  │
  └──────────────────────────────────────────────────┘
  Double entry references = Double pointer overhead on GC root tracing.
```

### The Live Inverse View Challenge
Senior engineers must know how the `inverse()` view is constructed. If you simply copy the maps when `inverse()` is called, you lose the **live-updating** feature. A true BiMap implementation (like Google Guava's) creates a proxy delegation wrapper. Both the forward and inverse maps share the *same physical references* to the underlying data stores. If you write to `inverse().put(Value, Key)`, it instantly updates the forward map.

### Thread Safety and Deadlock Risks
Making a BiMap thread-safe is much trickier than just slapping `synchronized` on every method. If you use standard locks on two separate maps inside a `put` method:

```java
// DANGER: DEADLOCK PRONE DESIGN
public synchronized V put(K key, V value) {
    synchronized(forwardMap) {
        synchronized(reverseMap) {
            // Write...
        }
    }
}
```

If another concurrent thread attempts to read or write starting from the `reverseMap` first, you risk a classic **deadlock (Lock-Ordering Bug)**. To make a high-throughput, concurrent BiMap, you must use a single lock (e.g., a shared `ReentrantReadWriteLock`) or implement a lock-free structure using a coordinated CAS (Compare-And-Swap) engine, which is highly complex to write from scratch.

---

### Interviewer Probes: Tricky Questions & Expert Answers

#### Probe 1: "Why can't we just use a single `HashMap` and store both `K -> V` and `V -> K` entries in it?"
* **Junior Answer:** "Because the keys and values might have the same types, and we could overwrite them or get confused about which is which."
* **Senior Answer:** "While storing both directions in a single map (`Map<Object, Object>`) avoids creating two map instances, it introduces severe type erasure and safety issues. You lose generic type safety (`BiMap<K, V>`). Furthermore, if a key and a value happen to have the identical value and type (e.g., mapping `Integer 5` to `Integer 5`), the internal node counts and collisions become hard to track, and operations like `size()` would return incorrect, halved counts because the forward and backward mappings overwrite each other."

#### Probe 2: "What happens to Garbage Collection (GC) in a BiMap if we dynamically remove keys?"
* **Junior Answer:** "They just get deleted and cleaned up by the GC."
* **Senior Answer:** "If your custom implementation fails to clean up *both* maps during a mutation or deletion, you create a memory leak. For example, if you remove an entry from `forwardMap` but forget to clear it from `reverseMap`, the object reference inside `reverseMap` prevents the garbage collector from reclaiming both the value *and* the key. To make a robust, memory-safe BiMap, we must ensure that any write, eviction, or clear operation is mirrored atomically across both structures."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Strict 1:1 Bijection:** A BiMap enforces that both Keys and Values are completely unique. If you attempt to map a key to an existing value, the operation is rejected.
2. **Double Map Storage:** Under the hood, a BiMap maintains two Maps (Forward and Reverse). This guarantees $O(1)$ lookups in both directions at the cost of $2\times$ memory.
3. **Live Inverse Views:** Calling `inverse()` should return a synchronized view, not a copied map. Changes to the inverse view must dynamically write through to the main map.

### 1 Golden Rule
> **"If you need fast reverse lookups, don't loop; use a BiMap. But always remember to prune both maps on deletion to prevent GC memory leaks."**