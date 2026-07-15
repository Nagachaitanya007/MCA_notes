---
title: The Bitmapped Vector Trie: Custom Persistent Immutable Lists
date: 2026-07-15T04:46:38.316739
---

# The Bitmapped Vector Trie: Custom Persistent Immutable Lists

---

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine you want a **List** that is completely **immutable** (it can never be changed after creation). If you want to add an element, you can't modify the existing list. 

The naive way to do this is to copy the entire array and add the new element to the end. This is safe, but it is incredibly slow—it takes $O(N)$ time. If your list has 1 million items, copying it takes 1 million operations just to add *one* item!

A **Bitmapped Vector Trie** is a highly optimized, tree-based data structure that gives you the best of both worlds. It acts like an array but is structured like a wide tree. When you add or update an item, it doesn't copy the whole list. Instead, it copies only a tiny path of nodes from the root to that leaf, while sharing all other unchanged branches with the old version. This is called **Structural Sharing**.

```
    [Old Version]             [New Version]
     Root (V1)                 Root (V2) (Newly created)
       /    \                   /    \
      /      \                 /      \
  Node A    Node B --------> Node A  Node B' (Newly copied path)
  (Shared)                           /    \
                                    /      \
                                Node C   New Leaf (Added element)
```

### Real-World Analogy
Think of a **Git repository**. When you make a commit that changes one line in a single file, Git doesn't duplicate your entire project folder on your hard drive. It creates a new commit object that points directly to the unchanged files of the previous commit, only creating a new version of the file you modified. 

The Bitmapped Vector Trie does exactly this, but at the memory level for elements in a list.

### Why should I care?
In modern high-throughput, multi-threaded applications, managing shared state is the number one source of bugs (race conditions, deadlocks). Standard concurrent collections use locks, which slow down your application.

With a persistent, structural-sharing collection:
1. **Thread-Safety is Free:** You can share your collection across 1,000 threads without a single lock or `synchronized` block. Threads can never read dirty or half-modified data.
2. **Zero-Cost Snapshots:** You can save a historical version of your collection instantly (in $O(1)$ time) without consuming extra memory.

---

## 2. 🛠️ How it Works (Step-by-Step)

To make this simple to understand, we will implement a simplified version with a **branching factor of 4** (using 2 bits to index each level). 
*(Note: Production systems like Scala or Clojure use a branching factor of 32, but the math and logic are identical).*

### The Step-by-Step Process:
1. **The Trie Structure:** The list is represented as a tree where every internal node has up to 4 children. The actual elements are stored only in the leaf nodes.
2. **Bitmapped Indexing:** To find an item at index `i`, we convert the index to binary and read it 2 bits at a time. Each 2-bit chunk tells us exactly which child array index to follow at each level.
3. **Path Copying (The Write Phase):** To add an element:
   - We allocate a new root.
   - We traverse down to where the new element should go.
   - For every node along that path, we clone its array of pointers, swap in the updated path, and attach it to the new root.
   - All branches *outside* of this path are pointed to directly by both the old and new nodes.

### Code Implementation (Java)

```java
import java.util.Arrays;

/**
 * A custom Persistent Immutable List using a 4-way Bitmapped Vector Trie.
 * For educational clarity, we use a branching factor of 4 (2 bits per level).
 */
public class PersistentVector<E> {
    private static final int BITS = 2; // 2 bits per level
    private static final int WIDTH = 1 << BITS; // 4 children per node
    private static final int MASK = WIDTH - 1; // 0x03 (binary 11)

    private final int size;
    private final int shift; // Represents the height of the trie (in bit-shifts)
    private final Node root;

    // Internal node structure
    private static class Node {
        final Object[] array;

        Node(Object[] array) {
            this.array = array;
        }
    }

    // Empty vector initializer
    public PersistentVector() {
        this.size = 0;
        this.shift = BITS;
        this.root = new Node(new Object[WIDTH]);
    }

    // Private constructor for generating new versions
    private PersistentVector(int size, int shift, Node root) {
        this.size = size;
        this.shift = shift;
        this.root = root;
    }

    public int size() {
        return this.size;
    }

    /**
     * Gets the element at a specific index.
     * Time Complexity: O(log_4 N) - effectively O(1).
     */
    @SuppressWarnings("unchecked")
    public E get(int index) {
        if (index < 0 || index >= size) {
            throw new IndexOutOfBoundsException("Index: " + index + ", Size: " + size);
        }
        Node node = root;
        // Traverse down the levels of the trie using bit shifts
        for (int level = shift; level > 0; level -= BITS) {
            int childIndex = (index >>> level) & MASK;
            node = (Node) node.array[childIndex];
        }
        return (E) node.array[index & MASK];
    }

    /**
     * Appends an element to the end of the vector, returning a NEW version.
     * Original vector remains untouched!
     */
    public PersistentVector<E> push(E value) {
        // Step 1: Check if the current tree has room.
        // If size fits within the maximum capacity of the current height:
        if (size < (1 << (shift + BITS))) {
            Node newRoot = pushRecursive(shift, root, size, value);
            return new PersistentVector<>(size + 1, shift, newRoot);
        }

        // Step 2: Tree is full! We must grow upwards (increase height).
        // Create a new root that points to the old root and a new branch.
        Node newRoot = new Node(new Object[WIDTH]);
        newRoot.array[0] = root;
        newRoot.array[1] = createPathToNewLeaf(shift, size, value);
        
        return new PersistentVector<>(size + 1, shift + BITS, newRoot);
    }

    // Recursively copies the active path down to the leaf level and inserts the value
    private Node pushRecursive(int level, Node current, int index, E value) {
        Object[] newArray = Arrays.copyOf(current.array, WIDTH);
        int childIndex = (index >>> level) & MASK;

        if (level == 0) {
            // We reached the leaf level! Put the value directly in the cloned array.
            newArray[childIndex] = value;
        } else {
            // We are at an internal node level.
            Node child = (Node) current.array[childIndex];
            if (child == null) {
                // Path does not exist yet; build a fresh branch down
                newArray[childIndex] = createPathToNewLeaf(level - BITS, index, value);
            } else {
                // Path exists; recursively clone and update down that path
                newArray[childIndex] = pushRecursive(level - BITS, child, index, value);
            }
        }
        return new Node(newArray);
    }

    // Helper to build a completely new structural branch down to the leaf
    private Node createPathToNewLeaf(int level, int index, E value) {
        Object[] array = new Object[WIDTH];
        int childIndex = (index >>> level) & MASK;
        if (level == 0) {
            array[childIndex] = value;
        } else {
            array[childIndex] = createPathToNewLeaf(level - BITS, index, value);
        }
        return new Node(array);
    }
}
```

### Visualizing Path Copying (Trie Depth = 2)

If we have 4 elements and want to append a 5th element:

```text
BEFORE PUSH:
                [Root V1]
               /         \
        [Leaf Node 0]   [Leaf Node 1]
         [A, B, C, D]    [E, null, null, null]

AFTER PUSH(F):
  [Root V1]                       [Root V2] (New Root!)
   /     \                         /     \
  /       \                       /       \
[Leaf0]  [Leaf1] <------------ [Leaf0]   [Leaf1-Copy] (Copied & Updated)
                                          [E, F, null, null]
                                              ^ Added
```
*Note how Leaf0 is completely shared between Version 1 and Version 2.*

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Math: Why is this considered $O(1)$?
In interviews, you might be challenged on the time complexity of reads and writes. Strictly speaking, operations are $O(\log_W N)$, where $W$ is the branching factor.

In production implementations (like Clojure), $W = 32$.
- $32^1 = 32$ elements
- $32^2 = 1,024$ elements
- $32^5 = 33,554,432$ elements
- $32^6 = 1,073,741,824$ elements (Over 1 Billion!)

This means for any collection up to 1 Billion elements, looking up or appending an item takes at most **6 hops**. Because 6 is a constant upper bound, computer scientists classify this as **Effectively $O(1)$** (constant time) with a very small constant factor.

### Trade-offs: Memory & CPU Performance

| Feature | Standard Array / ArrayList | Bitmapped Vector Trie (Persistent) |
| :--- | :--- | :--- |
| **Lookup Speed** | Absolute fastest (direct memory pointer index lookup). | Slightly slower (requires up to 6 bit-shift operations and array lookups). |
| **Update/Append Speed** | $O(1)$ amortized, but $O(N)$ when array resizing happens. | $O(\log_{32} N)$ always (virtually constant, no massive latency spikes). |
| **Memory Footprint** | Low (contiguous memory block, minor overhead). | Higher (each internal node wrapper object adds reference overhead). |
| **Thread Safety** | unsafe without manual locks / synchronization. | **100% thread-safe out-of-the-box** without lock overhead. |

---

### Interviewer Probe Questions

#### Probe 1: "Why is the branching factor set to exactly 32? Why not 2 (Binary Tree) or 1024?"
**Answer:** This is a balance of **CPU cache line efficiency** and **tree depth**.
- If we use $W = 2$ (binary tree), the tree becomes very deep ($\log_2 N$). For 1 million elements, we'd need 20 pointer hops. This results in terrible cache miss rates as the CPU has to jump around different memory addresses.
- If we use $W = 1024$, each path-copy update would require copying arrays of size 1024. This wastes CPU cycles copying unmodified adjacent references.
- At $W = 32$, each node contains an array of 32 references. On modern 64-bit JVMs, a 32-reference array is 256 bytes. This fits beautifully into modern CPU L1/L2 cache lines, allowing high-speed parallel access with minimal memory copying overhead during updates.

#### Probe 2: "If we do 1,000 updates in a row, won't we allocate thousands of throwaway path nodes and choke the Garbage Collector?"
**Answer:** Yes, doing naive sequential updates creates a lot of short-lived garbage. To solve this, production persistent collections use **Transients**. 

A transient is a temporary, mutable wrapper around the trie. During a batch operation, the transient allows us to mutate the node arrays *in-place* using a unique "epoch/owner" token. Once the batch modification is finished, the transient is frozen back into a highly-shared, read-only persistent vector. This reduces memory allocation during batch operations back down to $O(1)$ garbage generation.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Structural Sharing** allows us to create new versions of collections instantly by copying only the nodes on the direct path of change, pointing all other references back to the original tree branches.
2. **Bitmapped Indexing** uses bit-shifting and masking (`>>>` and `&`) to convert an integer index into direct array coordinates at each level of the tree, bypassing expensive division calculations.
3. **No-Lock Thread Safety:** Because the elements and nodes of a Bitmapped Vector Trie are 100% immutable, read operations never require synchronized locking structures, bypassing the thread contention bottleneck.

### 💡 The Golden Rule
> **"Copy the path, share the rest."** 
> When designing custom persistent collections, never duplicate the data you aren't changing. Clone only the pointers leading to the change, and let the rest of your new structure point to the old.