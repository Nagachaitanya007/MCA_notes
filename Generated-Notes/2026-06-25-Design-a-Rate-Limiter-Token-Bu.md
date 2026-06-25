---
title: Designing a Rate Limiter: Token Bucket vs Leaky Bucket
date: 2026-06-25T10:31:38.923594
---

# Designing a Rate Limiter: Token Bucket vs Leaky Bucket

1. 💡 The "Big Picture" (Plain English):
   - A rate limiter is like a bouncer at a nightclub. It controls how many people can enter the club within a certain time frame, preventing it from getting too crowded.
   - Imagine a restaurant with a limited number of tables. The rate limiter ensures that not too many customers try to get a table at the same time, preventing the staff from getting overwhelmed.
   - You should care about rate limiters because they help prevent your application or service from being overwhelmed by too many requests, which can lead to performance issues, crashes, or even security vulnerabilities.

2. 🛠️ How it Works (Step-by-Step):
   - **Token Bucket Algorithm:**
     1. Imagine a bucket that can hold a certain number of tokens.
     2. Tokens are added to the bucket at a constant rate.
     3. When a request is made, a token is removed from the bucket.
     4. If the bucket is empty, the request is blocked until a token is added.
   - **Leaky Bucket Algorithm:**
     1. Imagine a bucket with a leaky hole at the bottom.
     2. Water (representing requests) is poured into the bucket at a variable rate.
     3. The bucket leaks at a constant rate.
     4. If the bucket overflows, the excess water is discarded (requests are blocked).
   - Here's a simple code snippet in Python to illustrate the token bucket algorithm:
     ```python
import time

class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    def consume(self, tokens):
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        else:
            return False
```
   - Here's a Mermaid diagram to show the flow:
     ```mermaid
graph LR
    A[Request] -->|Token Available?|> B[Yes]
    A -->|No|> C[Wait/Block]
    B --> D[Send Request]
    D --> E[Update Token Count]
    E --> F[Check Token Count]
    F -->|Enough Tokens?|> B
    F -->|Not Enough Tokens|> C
```

3. 🧠 The "Deep Dive" (For the Interview):
   - **Technical 'Magic':** The token bucket algorithm is based on the idea of a token bucket, where tokens are added at a constant rate and removed when a request is made. The leaky bucket algorithm is based on the idea of a bucket with a leaky hole, where water (requests) is poured in at a variable rate and leaks out at a constant rate.
   - **Trade-offs:** The token bucket algorithm is more flexible and allows for bursts of traffic, but it can be more complex to implement. The leaky bucket algorithm is simpler to implement, but it can be less flexible and may block requests more frequently.
   - **Interviewer Probe Questions:**
     1. How would you implement a rate limiter in a distributed system, where multiple nodes need to coordinate their rate limiting decisions?
     2. What are some potential issues with using a token bucket algorithm in a system with variable-rate traffic, and how would you mitigate these issues?
     3. How would you choose between a token bucket and a leaky bucket algorithm for a given use case, and what are the key factors to consider in making this decision?

4. ✅ Summary Cheat Sheet:
   - **3 Key Takeaways:**
     1. Rate limiters are essential for preventing applications and services from being overwhelmed by too many requests.
     2. The token bucket algorithm is more flexible and allows for bursts of traffic, while the leaky bucket algorithm is simpler to implement but less flexible.
     3. The choice between a token bucket and a leaky bucket algorithm depends on the specific use case and the trade-offs between flexibility, complexity, and performance.
   - **Golden Rule:** Always consider the trade-offs between flexibility, complexity, and performance when designing a rate limiter, and choose the algorithm that best fits the specific needs of your application or service.