---
title: Handling Downstream Backpressure: Dynamic Rate-Limiting in SQS-to-Webhook Dispatching
date: 2026-07-12T10:32:15.245227
---

# Handling Downstream Backpressure: Dynamic Rate-Limiting in SQS-to-Webhook Dispatching

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
When we build a notification system, our system is often a Ferrari (insanely fast, processing millions of events per second via Kafka). But our customers’ servers—the ones receiving our webhooks—might be old family sedans (they can only handle 10 requests per second before breaking down). 

**Dynamic Rate-Limiting and Backpressure Management** is the traffic cop that sits between our super-fast engine (SQS) and our customers' fragile servers. It makes sure we only send them messages as fast as they can handle them, slowing down automatically if their servers start to struggle.

### A Real-World Analogy
Imagine you run a super-efficient pizza delivery kitchen. Your chefs (Kafka) can bake 1,000 pizzas a minute. You have a fleet of delivery drivers (SQS & Webhook Dispatchers). 

If you send 100 delivery drivers to a tiny apartment building all at the same time, the lobby gets clogged, the residents panic, and the building security guard shuts down the entrance. 

Instead, a smart dispatcher monitors the lobby. If the lobby is full, the dispatcher tells the drivers to wait at the pizza shop, or drive around the block for 5 minutes before trying again.

### Why should I care?
If you don't build this:
1. **You will accidentally DDoS your own customers.** You will overwhelm their servers, they will block your IP, and they will leave your service.
2. **You will waste money and compute resources.** Your workers will constantly try to send messages, get rejected with `429 Too Many Requests` or `503 Service Unavailable`, and endlessly retry in a tight, CPU-burning loop.

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Architecture Flow

```mermaid
sequenceDiagram
    autonumber
    participant SQS as SQS Queue
    participant WD as Webhook Dispatcher (Worker)
    participant Redis as Redis (Rate-Limiter State)
    participant Cust as Customer Server
    
    WD->>SQS: Poll for message
    SQS-->>WD: Return webhook event
    WD->>Redis: Check current lease count / rate limit
    alt Rate Limit Exceeded
        Redis-->>WD: Rejected (Over limit)
        WD->>SQS: Change Message Visibility (Put back with delay)
    else Under Limit
        Redis-->>WD: Allowed (Increment lease)
        WD->>Cust: POST /webhook (Send Event)
        alt Success (200 OK)
            Cust-->>WD: 200 OK
            WD->>SQS: Delete message
        alt Backpressure (429 Too Many Requests)
            Cust-->>WD: 429 Too Many Requests (Retry-After: 30s)
            WD->>Redis: Temporarily lower rate-limit for tenant
            WD->>SQS: Change Message Visibility to 30 seconds
        end
    end
```

### The Step-by-Step Code Implementation (TypeScript)

Here is how a webhook worker handles polling, checking rate limits against Redis, dispatching, and dynamically backing off if the customer’s API is overwhelmed.

```typescript
import { SQSClient, ChangeMessageVisibilityCommand, DeleteMessageCommand } from "@aws-sdk/client-sqs";
import Redis from "ioredis";
import axios from "axios";

const sqs = new SQSClient({ region: "us-east-1" });
const redis = new Redis();

interface WebhookPayload {
  tenantId: string;
  url: string;
  data: any;
  receiptHandle: string; // SQS identifier to delete/delay the message
}

async function processWebhook(message: WebhookPayload) {
  const { tenantId, url, data, receiptHandle } = message;
  const rateLimitKey = `rate_limit:${tenantId}`;

  // 1. Check with Redis if this tenant has exceeded their allowed concurrent request limit
  const isRateLimited = await redis.get(`backoff:${tenantId}`);
  if (isRateLimited) {
    // Over limit! Back off immediately without calling the customer's server.
    console.warn(`Tenant ${tenantId} is backed off. Putting message back to SQS.`);
    await delaySQSMessage(receiptHandle, 30); // Delay for 30 seconds
    return;
  }

  try {
    // 2. Dispatch the HTTP POST request to the customer's server
    const response = await axios.post(url, data, { timeout: 5000 });

    if (response.status === 200) {
      // Success! Remove from SQS queue
      await deleteSQSMessage(receiptHandle);
    }
  } catch (error: any) {
    if (error.response && error.response.status === 429) {
      // 3. Customer returned 429 (Too Many Requests). Read 'Retry-After' header or default to 60s
      const retryAfterSeconds = parseInt(error.response.headers['retry-after'] || '60', 10);
      
      console.warn(`Rate limit hit for tenant ${tenantId}. Backing off for ${retryAfterSeconds}s`);
      
      // Mark this tenant as rate-limited in Redis (the "circuit breaker" flag)
      await redis.setex(`backoff:${tenantId}`, retryAfterSeconds, "true");
      
      // 4. Update SQS Visibility Timeout so this message isn't processed again until the backoff expires
      await delaySQSMessage(receiptHandle, retryAfterSeconds);
    } else {
      // Handle generic errors (500s, timeouts) with standard exponential backoff
      await delaySQSMessage(receiptHandle, 10); 
    }
  }
}

async function delaySQSMessage(receiptHandle: string, delayInSeconds: number) {
  const command = new ChangeMessageVisibilityCommand({
    QueueUrl: process.env.SQS_QUEUE_URL,
    ReceiptHandle: receiptHandle,
    VisibilityTimeout: delayInSeconds
  });
  await sqs.send(command);
}

async function deleteSQSMessage(receiptHandle: string) {
  const command = new DeleteMessageCommand({
    QueueUrl: process.env.SQS_QUEUE_URL,
    ReceiptHandle: receiptHandle
  });
  await sqs.send(command);
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic: How it Works Under the Hood

#### 1. SQS Visibility Timeout Manipulation
Instead of keeping a worker thread asleep (which blocks precious compute resources), we use SQS's native `ChangeMessageVisibility` API. 
* When a worker pulls a message, the message becomes "invisible" to other workers for a default period (e.g., 30 seconds).
* If we detect that the downstream consumer is rate-limiting us, we immediately set the visibility timeout of that specific message to a high value (e.g., 120 seconds) and finish the thread.
* The message stays safely stored in SQS, completely invisible to all other workers until the timer runs out, preventing redundant retries.

#### 2. Distributed Sliding Window Rate Limiting (Redis + Lua)
To enforce rate limits across dozens of autoscaling webhook workers, we use Redis. Using simple HTTP checks in TypeScript can lead to **race conditions** (two workers checking the rate limit at the exact same microsecond, both seeing they are under the limit, and both sending a request, exceeding the limit).

We solve this using a **Redis Lua script**. Lua scripts execute atomically inside Redis, ensuring that rate-limiting checks-and-increments happen as a single, uninterrupted transaction.

```lua
-- Lua script running inside Redis
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('get', key) or "0")

if current + 1 > limit then
    return 0 -- Rejected (Rate limit reached)
else
    redis.call("INCRBY", key, 1)
    redis.call("EXPIRE", key, 1) -- 1 second sliding window
    return 1 -- Allowed
end
```

### Trade-offs: What's the Catch?

| Architecture Choice | Pros | Cons |
| :--- | :--- | :--- |
| **Shared Queue + Redis Tracking** | Simple to manage; single queue infrastructure; cost-efficient on SQS. | **Head-of-Line Blocking**: If Tenant A is heavily rate-limited, their messages might choke the queue, delaying Tenant B's healthy traffic. |
| **Per-Tenant SQS Queues** | Perfect isolation; Tenant A's backpressure never impacts Tenant B. | High AWS operational overhead; hard to scale dynamically to tens of thousands of tenants. |
| **Token Bucket in Redis** | Highly precise traffic shaping; supports bursts of traffic smoothly. | Puts massive write load on Redis; if Redis crashes, you lose all rate limit states. |

---

### Interviewer Probe Questions (How they will test you)

#### Question 1: "If one customer's server goes down and enters a 429 loop, how do you prevent their failing webhooks from causing delay (Head-of-Line blocking) for other customers?"
* **Your Answer:** "If we use a single shared queue, a failing tenant's messages will continuously fail, get put back into the queue, and monopolize our worker threads. To prevent this, we implement **Virtual Queuing with Shunting**. When a tenant begins returning 429s, we shunt their incoming messages to a dedicated 'Slow/Retry Queue' or mark them in Redis. Workers pull from the main queue first, and only process the slow queue with a small, throttled pool of dedicated 'slow workers'. This isolates the impact to the failing tenant."

#### Question 2: "What happens if Redis goes down? How does your rate-limiting dispatcher react?"
* **Your Answer:** "We must design our rate-limiter to **fail-open** rather than **fail-closed**. If Redis throws an error, the code should catch the exception, log a high-severity alert, and fallback to a local, in-memory rate-limiter (like a LRU cache) on each worker instance. This prevents a Redis outage from completely stopping our entire notification delivery system, even if it temporarily risks over-sending webhooks."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Never block worker threads:** Don't use `setTimeout` or `sleep()` to wait out a rate limit. Use SQS `ChangeMessageVisibility` to return the message to the queue with a delay, freeing your workers to process healthy traffic.
2. **Handle 429s gracefully:** Inspect the `Retry-After` header sent by downstream systems. Treat it as a direct instruction to adjust your rate-limiting timers.
3. **Use Atomic Operations:** Implement rate limit counters in Redis using **Lua scripts** to avoid concurrency race conditions across distributed workers.

### 1 Golden Rule
> **"Respect the downstream."** An outstanding notification system isn't just about how fast you can push events out—it is about how gracefully you slow down to match the limits of the systems receiving them.