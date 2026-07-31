---
title: Handling Mass Fan-out and Redis Memory Limits in Large-Scale Group Chat Systems
date: 2026-07-31T10:32:06.415416
---

# Handling Mass Fan-out and Redis Memory Limits in Large-Scale Group Chat Systems

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
Imagine sending a message to one friend in a chat app—that’s simple, like passing a sticky note. Now imagine sending a message to a group chat with **100,000 people** online at the exact same moment. 

If your backend server tries to send 100,000 individual messages one by one, it will freeze, memory will spike, and the system will crash. **Mass Fan-out Optimization** is the engineering strategy used to distribute a single message to hundreds of thousands of concurrent WebSocket connections efficiently without crashing your infrastructure or melting Redis.

#### Real-world Analogy
Imagine a busy airport terminal. 
* **Bad Approach (Unoptimized Fan-out):** The airport gate agent walks up to all 500 waiting passengers individually and whispers, *"Flight 101 is now boarding."* By the time they reach passenger #500, the plane has already left.
* **Good Approach (Optimized Fan-out):** The agent speaks into a single microphone connected to localized zone loudspeakers. The sound system handles broadcasting to thousands of ears simultaneously without the agent taking an extra step.

#### Why should I care? What problem does it solve for me today?
If you build a real-time chat app, live streaming comment section, or collaborative tool (like Figma or Slack), you will eventually hit a **"celebrity effect"** or **"mega-group problem."** Without fan-out optimization:
1. **Redis crashes with Out-Of-Memory (OOM)** errors due to pub/sub output buffer bloat.
2. **WebSocket node event loops lock up**, blocking heartbeats and disconnecting tens of thousands of healthy users.
3. **P99 latency spikes** from 10 milliseconds to 15+ seconds.

---

### 2. 🛠️ How it Works (Step-by-Step)

#### Process Breakdown

```
[Sender Client] 
      │ 1. POST /chat/message
      ▼
[API Gateway / Ingestion Service]
      │ 2. Publish to Redis Pub/Sub (Single payload)
      ▼
┌────────────────────────────────────────────────────────┐
│                      REDIS CLUSTER                     │
└───────────────────────────┬────────────────────────────┘
                            │ 3. Broadcast to subscribed nodes only
            ┌───────────────┴───────────────┐
            ▼                               ▼
    [WebSocket Node 1]              [WebSocket Node 2]
    (Has 3,000 local listeners)     (Has 2,000 local listeners)
            │                               │
            │ 4. Batch local fan-out        │ 4. Batch local fan-out
            │    (Non-blocking loops)       │    (Non-blocking loops)
            ▼                               ▼
    [Users 1..3000]                 [Users 3001..5000]
```

1. **Ingestion & Single Publish:** A user sends a message to room `channel-gold-traders` (100k members). The API server writes the message to the database and publishes **one single copy** to Redis Pub/Sub.
2. **Node-Level Subscription Filtering:** WebSocket servers only subscribe to Redis channels for rooms where they currently hold at least **one active WebSocket connection**.
3. **Local Socket Partitioning:** Upon receiving the Redis message, the WebSocket server looks up its local memory map (`Map<RoomID, Set<WebSocket>>`) to identify only the local users on *that specific server*.
4. **Batched Non-Blocking Fan-out:** The server iterates through local sockets in CPU-friendly chunks (e.g., 500 sockets per event loop tick) while checking socket write buffers to avoid choking slow client connections.

#### Implementation Example (Node.js/TypeScript)

Here is a resilient WebSocket node engine handling high-concurrency fan-out safely:

```typescript
import WebSocket, { WebSocketServer } from 'ws';
import Redis from 'ioredis';

const redisSub = new Redis({ host: '127.0.0.1', port: 6379 });
const wss = new WebSocketServer({ port: 8080 });

// Local registry: Maps Room ID -> Set of active WebSocket connections on THIS node
const roomLocalSockets = new Map<string, Set<WebSocket>>();

// Subscribed Redis channels tracker to prevent redundant subscriptions
const activeRedisSubscriptions = new Set<string>();

// Handle Incoming WebSocket Connections
wss.on('connection', (ws: WebSocket, req) => {
  const roomId = getRoomFromUrl(req.url); // e.g., "room:crypto-chat"

  // 1. Add connection to local registry
  if (!roomLocalSockets.has(roomId)) {
    roomLocalSockets.set(roomId, new Set());
  }
  roomLocalSockets.get(roomId)!.add(ws);

  // 2. Dynamically subscribe to Redis channel ONLY if this is the first local connection
  if (!activeRedisSubscriptions.has(roomId)) {
    redisSub.subscribe(roomId);
    activeRedisSubscriptions.add(roomId);
  }

  ws.on('close', () => {
    const sockets = roomLocalSockets.get(roomId);
    if (sockets) {
      sockets.delete(ws);
      // Clean up empty room state to avoid memory leaks
      if (sockets.size === 0) {
        roomLocalSockets.delete(roomId);
        redisSub.unsubscribe(roomId);
        activeRedisSubscriptions.delete(roomId);
      }
    }
  });
});

// 3. Receive Pub/Sub message from Redis and Fan-out locally
redisSub.on('message', (channel: string, messagePayload: string) => {
  const localSockets = roomLocalSockets.get(channel);
  if (!localSockets || localSockets.size === 0) return;

  // Convert Set to Array for chunked processing
  const socketArray = Array.from(localSockets);
  const CHUNK_SIZE = 500; // Do not block the thread with huge loops
  let index = 0;

  function processChunk() {
    const chunkEnd = Math.min(index + CHUNK_SIZE, socketArray.length);

    for (; index < chunkEnd; index++) {
      const socket = socketArray[index];

      // Check socket state and Backpressure (bufferedAmount)
      if (socket.readyState === WebSocket.OPEN) {
        // If the client's socket buffer > 1MB, drop or yield to prevent OOM
        if (socket.bufferedAmount > 1024 * 1024) {
          console.warn('Slow consumer detected. Dropping non-critical message.');
          continue; 
        }
        socket.send(messagePayload);
      }
    }

    // Yield control back to event loop before processing next batch
    if (index < socketArray.length) {
      setImmediate(processChunk);
    }
  }

  processChunk();
});

function getRoomFromUrl(url?: string): string {
  return url?.split('?room=')[1] || 'default-room';
}
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### Redis Pub/Sub Buffer Limits & The "Slow Consumer" Trap
Redis Pub/Sub is **fire-and-forget**. It does not store messages on disk or back them up in a queue. Every subscriber (WebSocket node) connected to Redis has an outbound client buffer in Redis memory.

When a single group chat generates a flood of messages, Redis attempts to push these bytes to every subscribed WebSocket node. If Node A is busy processing a heavy synchronous operation or experiencing garbage collection (GC) pauses, its TCP receive window shrinks. 

Redis buffers those un-acknowledged bytes in RAM. If they breach the configured threshold:
```text
# redis.conf setting
client-output-buffer-limit pubsub 32mb 8mb 60
```
*(Meaning: If a subscriber exceeds 32MB immediately OR sustains 8MB for 60 seconds, Redis forcefully disconnects the subscriber).*

**Result:** The WebSocket server loses its Redis connection, misses hundreds of real-time messages, and enters a reconnect loop—causing systemic cascade failures.

```
┌─────────────────────────────────────────────────────────────┐
│                       REDIS INSTANCE                        │
│                                                             │
│  [ Published Msg ] ──► [ Node 1 Buffer (Fast) ] ──► Sent OK │
│                    ──► [ Node 2 Buffer (Slow) ] ──► BLOAT!  │
└──────────────────────────────────────────────────┬──────────┘
                                                   │
                          Exceeds 32MB Limit?      ▼
                                           [ REDIS KICKS NODE 2 ]
```

#### Hybrid Fan-out Strategy: Push vs. Pull Thresholds
To scale past 100,000+ active users in a single channel (e.g., Twitch chat, breaking news stream), pure WebSockets + Redis Pub/Sub breaks down. You must implement a **Hybrid Fan-out Architecture**:

| Room Size (Concurrents) | Transport Strategy | Fan-out Mechanism |
| :--- | :--- | :--- |
| **Small (< 1,000)** | WebSockets | Direct Redis Pub/Sub push to all connections. |
| **Medium (1k - 10k)** | WebSockets | Local node batched chunking + backpressure checks. |
| **Mega (100k+)** | Server-Sent Events (SSE) or HTTP/2 Pull | **Edge CDN Caching**: Clients poll/stream from an edge HTTP worker (Cloudflare Workers, Fastly) that reads cached message chunks from Redis/S3 every 500ms. |

#### Trade-offs Matrix

| Design Choice | Pros | Cons |
| :--- | :--- | :--- |
| **1 Channel Per Room** | Precise routing; zero wasted bandwidth on WebSocket nodes. | Millions of rooms = high Redis memory overhead for subscription hash tables. |
| **Sharded Redis Channels** (e.g., `room-hash-mod-64`) | Keeps Redis channel counts low and constant. | WebSocket nodes receive messages for rooms they don't host; requires local filtering overhead. |
| **Synchronous Local Socket Loops** | Simple code; low latency for small groups. | Blocks the event loop on huge rooms, delaying heartbeat PING/Pongs and dropping connections. |

#### Interviewer Probe Questions

##### Probe 1: "What happens if a Redis node hosting Pub/Sub crashes? How do users get missed messages?"
* **Answer:** Since Redis Pub/Sub is ephemeral and unpersisted, all messages published during the failover window are lost. To handle this gracefully:
  1. Messages are written to a persistent database (Cassandra, ScyllaDB, or Postgres) *before* or *concurrently with* publishing.
  2. The client detects the WebSocket disconnect/reconnect sequence and requests missing messages via REST/gRPC using a `last_message_id` sequence token (`GET /messages?room=X&since=10492`).

##### Probe 2: "How do you protect a WebSocket node from running out of memory if a connected mobile client on a 2G network falls behind?"
* **Answer:** By leveraging TCP socket level backpressure and monitoring the OS/runtime socket buffer (`socket.bufferedAmount` in WebSockets). If a client is slow to consume bytes, `bufferedAmount` grows. Once it hits a safety threshold (e.g., 1MB), the server can:
  * Drop lower-priority non-text events (e.g., typing indicators, read receipts).
  * Sever the slow connection gracefully, forcing the client to reconnect and fetch missed history via pagination when their network stabilizes.

##### Probe 3: "Why use Redis Pub/Sub over Kafka or RabbitMQ for real-time WebSocket fan-out?"
* **Answer:** 
  * **Redis Pub/Sub** provides ultra-low sub-millisecond latency with near-zero setup overhead and light memory footprint per subscriber, making it ideal for transient frame delivery.
  * **Kafka** is designed for high-throughput, log-based, replayable message streaming, but introduces higher end-to-end delivery latency (10-50ms) and partition rebalancing overhead when WebSocket nodes dynamically scale up/down.
  * *Best Practice:* Use Kafka for persistent messaging pipelines (storage, analytics, audit logs) and pass the fan-out duty to Redis Pub/Sub or Redis Streams for real-time edge distribution.

---

### 4. ✅ Summary Cheat Sheet

```
+-----------------------------------------------------------------------+
|                       FAN-OUT CHEAT SHEET                             |
+-----------------------------------------------------------------------+
| 1. Dynamic Subscriptions : Only subscribe WS nodes to Redis channels  |
|                            for rooms hosted ON THAT NODE.             |
| 2. Local Batching        : Chunk local socket iteration with          |
|                            `setImmediate` to keep event loops free.  |
| 3. Buffer Protection     : Monitor `socket.bufferedAmount` & configure |
|                            Redis `client-output-buffer-limit`.        |
+-----------------------------------------------------------------------+
```

#### 3 Key Takeaways
1. **Never iterate over all connections synchronously:** Always process large fan-outs in asynchronous batches to keep the single-threaded event loop alive for heartbeats and new connections.
2. **Redis Pub/Sub is for signaling, not storage:** It lacks durability. Always back it with a real database and rely on sequence IDs (`last_seen_id`) for reconnection catch-up.
3. **Respect Backpressure:** A single slow mobile user on a bad connection must never be allowed to queue infinite bytes in server memory.

#### 1 "Golden Rule"
> **Publish once to the network, filter locally at the node, and degrade gracefully at the edge when room size scales exponentially.**