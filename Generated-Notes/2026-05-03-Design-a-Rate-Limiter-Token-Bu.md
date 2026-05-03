---
title: Choosing Your Throttle: Token Bucket vs. Leaky Bucket
date: 2026-05-03T10:31:25.733497
---

# Choosing Your Throttle: Token Bucket vs. Leaky Bucket

1. 💡 **The "Big Picture" (Plain English):**
   - **What is this?** Imagine your backend server is a small coffee shop. If 100 people rush the door at the exact same second, the barista crashes. A Rate Limiter is the "bouncer" at the door who decides who gets in and when.
   - **The Analogy:** 
     - **Token Bucket:** Imagine a jar that gets one "entry coupon" every second. If no one shows up for 10 seconds, the jar has 10 coupons. A group of 5 friends can walk in instantly using 5 coupons (**Bursting**).
     - **Leaky Bucket:** Imagine a funnel. You can pour a gallon of water in at once, but it only drips out the bottom at one drop per second. It forces a **constant, smooth flow** regardless of how fast you pour.
   - **Why care?** Without this, a single buggy loop in a client's code (or a DDoS attack) can take down your entire database. It’s the difference between a "Service Unavailable" error for one user and a total system meltdown for everyone.

2. 🛠️ **How it Works (Step-by-Step):**

### Token Bucket (The "Burst-Friendly" Choice)
1. A bucket has a maximum capacity ($N$).
2. A "refiller" adds tokens at a fixed rate (e.g., 10 tokens/sec).
3. If the bucket is full, new tokens are discarded.
4. When a request arrives, it tries to grab a token. If it succeeds, the request goes through. No token? Request is rejected (429 Too Many Requests).

```python
import time

class TokenBucket:
    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.fill_rate = fill_rate # tokens per second
        self.tokens = capacity
        self.last_fill = time.time()

    def allow_request(self, tokens_needed=1):
        # Calculate how many tokens were generated since the last request
        now = time.time()
        added_tokens = (now - self.last_fill) * self.fill_rate
        self.tokens = min(self.capacity, self.tokens + added_tokens)
        self.last_fill = now

        if self.tokens >= tokens_needed:
            self.tokens -= tokens_needed
            return True
        return False
```

### Leaky Bucket (The "Traffic Shaper")
1. Requests enter a queue (the bucket).
2. If the queue is full, the request is dropped.
3. A separate process "leaks" requests from the bottom at a strictly constant rate.

**The Flow:**
```text
[Requests: ⚡ ⚡ ⚡] -> |‾‾‾‾‾‾‾‾‾‾‾‾‾‾| 
                       |   Bucket     |  <-- "Smoothing out the spikes"
                       |_ _ _ _ _ _ _ |
                             | 💧
                             v
                       [Process 1/sec]
```

3. 🧠 **The "Deep Dive" (For the Interview):**

- **The "Atomic" Problem:** In a real-world distributed system (like using Redis), the "Check-then-Set" logic in the code above has a **Race Condition**. If two servers check the token count at the same millisecond, they might both see "1 token left" and both allow a request. 
  - *Senior Solution:* Use **Redis Lua Scripts**. Lua scripts execute atomically in Redis, ensuring no two requests can grab the last token simultaneously.

- **Memory vs. Precision:** 
  - **Token Bucket** is incredibly memory efficient. You only need to store two numbers: `last_refill_timestamp` and `current_token_count`. You don't need a timer running in the background; you calculate the "drift" lazily when a request arrives.
  - **Leaky Bucket** (as a queue) requires memory to hold the actual request data while they wait to be processed.

- **The Trade-offs:**
  - **Token Bucket:** Best for modern APIs. It allows **bursts**. If a user refreshes a page and triggers 5 API calls at once, Token Bucket allows it (as long as they haven't exceeded their minute limit).
  - **Leaky Bucket:** Best for background processing or interacting with legacy systems that *physically cannot* handle a burst. It guarantees a stable load.

- **Interviewer Probes:**
  1. *“How do you handle a distributed environment?”* Mention **sticky sessions** (simple but bad) vs. **centralized state** (Redis) vs. **distributed algorithms** (Generic Cell Rate Algorithm - GCRA).
  2. *“What happens if the Rate Limiter service goes down?”* Discuss **Fail-Open vs. Fail-Closed**. (Usually, we Fail-Open to avoid killing the UX, but we log the event heavily).

4. ✅ **Summary Cheat Sheet:**

- **3 Key Takeaways:**
    1. **Token Bucket** allows bursts but can be "spiky."
    2. **Leaky Bucket** forces a smooth, constant flow but can add latency to requests stuck in the queue.
    3. **Implementation:** Use Redis + Lua for atomicity in distributed systems.

- **The Golden Rule:**
  > "If you want to support a snappy UI where users might trigger multiple actions quickly, use **Token Bucket**. If you need to protect a fragile downstream database from ever seeing a spike, use **Leaky Bucket**."