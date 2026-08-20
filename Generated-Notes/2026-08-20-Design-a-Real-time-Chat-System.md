---
title: Real-Time Ephemeral Message Routing and Channel Multiplexing with Redis Pub/Sub
date: 2026-08-20T10:31:59.305088
---

# Real-Time Ephemeral Message Routing and Channel Multiplexing with Redis Pub/Sub

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
When you send a chat message, your phone doesn't repeatedly ask the server, *"Any new messages yet?"* (polling). Instead, it keeps an open, persistent wire to the server called a **WebSocket**. 

When users are connected to different servers across a cluster, **Redis Pub/Sub** acts as the central radio broadcast network. It delivers your message to the exact server where your friend is currently connected, which then pushes it straight down their open WebSocket in milliseconds.

```
[User A] ──(WebSocket)──► [Gateway Server 1]
                                 │ (PUBLISH)
                                 ▼
                         [Redis Pub/Sub]
                                 │ (SUBSCRIBE)
                                 ▼
[User B] ◄──(WebSocket)── [Gateway Server 2]
```

#### Real-World Analogy
Think of an **Airport Intercom System**:
- **WebSocket:** You sitting at **Gate B4**, listening directly to that gate's dedicated loudspeaker.
- **WebSocket Gateway Server:** The flight attendant standing at Gate B4 with a microphone connected to the airport network.
- **Redis Pub/Sub:** The central airport radio dispatch. When an announcement is made for *"Flight 102 to London,"* dispatch broadcasts it to all gate speakers. Only the gate hosting *Flight 102* plays the announcement through its local speaker to the waiting passengers.

#### Why should I care?
Without persistent WebSockets, apps drain battery and bandwidth by constantly polling HTTP endpoints. Without Redis Pub/Sub connecting the servers, User A (connected to Server 1) would never be able to talk to User B (connected to Server 2) in a horizontally scaled system.

---

### 2. 🛠️ How it Works (Step-by-Step)

```
       User A                      Gateway Node 1                     Redis Pub/Sub                   Gateway Node 2                      User B
         │                               │                                  │                               │                               │
         │  1. Send Chat Message         │                                  │                               │                               │
         │──────────────────────────────►│                                  │                               │                               │
         │                               │  2. PUBLISH room:42 "payload"    │                               │                               │
         │                               │─────────────────────────────────►│                               │                               │
         │                               │                                  │  3. Fan-out to Subscribers    │                               │
         │                               │                                  │──────────────────────────────►│                               │
         │                               │                                  │                               │  4. Lookup local sockets      │
         │                               │                                  │                               │     in room:42                │
         │                               │                                  │                               │  5. Push Frame via WebSocket  │
         │                               │                                  │                               │──────────────────────────────►│
```

1. **Connection & Multiplexing:** User B connects to Gateway Node 2. Node 2 registers User B’s WebSocket in an in-memory map: `Map<RoomId, Set<WebSocket>>`.
2. **Channel Subscription:** Gateway Node 2 subscribes to the Redis topic `room:42` using a single, shared Redis connection.
3. **Dispatch:** User A sends a message to Gateway Node 1 over its WebSocket. Gateway Node 1 publishes the message to Redis on topic `room:42`.
4. **Broadcast & Fan-Out:** Redis delivers the payload to all gateway nodes subscribed to `room:42`.
5. **Local Delivery:** Gateway Node 2 receives the Redis message, checks its local memory map for `room:42`, finds User B's socket, and immediately writes the frame down to User B.

#### Minimal Node.js / TypeScript Implementation

```typescript
import { WebSocketServer, WebSocket } from 'ws';
import Redis from 'ioredis';

const wss = new WebSocketServer({ port: 8080 });
const redisPub = new Redis();
const redisSub = new Redis(); // Dedicated connection for SUBSCRIBE

// In-Memory Registry: roomId -> Set of local WebSockets
const localRooms = new Map<string, Set<WebSocket>>();

// Listen for messages from Redis and push to local sockets
redisSub.on('message', (channel: string, message: string) => {
  const sockets = localRooms.get(channel);
  if (!sockets) return;

  for (const socket of sockets) {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(message);
    }
  }
});

wss.on('connection', (ws: WebSocket) => {
  let currentRoom: string | null = null;

  ws.on('message', async (raw: string) => {
    const data = JSON.parse(raw.toString());

    // 1. Join a channel/room
    if (data.action === 'JOIN') {
      currentRoom = data.roomId;
      
      if (!localRooms.has(currentRoom)) {
        localRooms.set(currentRoom, new Set());
        // Subscribe to Redis ONLY if this node hasn't subscribed yet
        await redisSub.subscribe(currentRoom);
      }
      localRooms.get(currentRoom)!.add(ws);
    }

    // 2. Send message to channel
    if (data.action === 'SEND' && currentRoom) {
      const payload = JSON.stringify({
        sender: data.userId,
        text: data.text,
        timestamp: Date.now(),
      });
      // Publish once to Redis; Redis handles cross-node distribution
      await redisPub.publish(currentRoom, payload);
    }
  });

  ws.on('close', () => {
    if (currentRoom && localRooms.has(currentRoom)) {
      const sockets = localRooms.get(currentRoom)!;
      sockets.delete(ws);
      
      // Cleanup: Unsubscribe from Redis if no local clients remain
      if (sockets.size === 0) {
        localRooms.delete(currentRoom);
        redisSub.unsubscribe(currentRoom);
      }
    }
  });
});
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### 1. The Single Connection vs. Connection Pool Trap
A junior engineer might create a new Redis connection for every WebSocket client. 

* **The Problem:** Redis is single-threaded for command execution. Creating 50,000 Redis connections for 50,000 WebSocket clients on a single gateway exhausts OS file descriptors and crashes Redis via memory overhead (each Redis client buffer consumes memory).
* **The Solution:** **Connection Multiplexing.** A gateway node maintains **exactly one** dedicated subscriber connection to Redis. That single connection subscribes to all active rooms on that node and routes incoming messages to local sockets via an in-memory routing table (`Map<string, Set<WebSocket>>`).

#### 2. Redis Pub/Sub Buffer Overflow (`client-output-buffer-limit`)
Redis Pub/Sub is **at-most-once** and **ephemeral**—it has no message history or disk persistence. 

If Gateway Node 2 experiences an event loop lag or network slow-down, Redis buffers outgoing messages in memory for that subscriber. 

If this buffer exceeds the configured limits:
```text
client-output-buffer-limit pubsub 32mb 8mb 60
```
*(Meaning: Hard limit of 32MB, or soft limit of 8MB continuously for 60 seconds)*

Redis will **forcibly terminate the connection to Gateway Node 2** to protect its own memory. Gateway Node 2 must handle reconnecting and re-subscribing to all active channels immediately, during which in-flight messages are permanently dropped.

#### 3. Trade-Offs: Redis Pub/Sub vs. Redis Streams vs. Kafka

| Dimension | Redis Pub/Sub | Redis Streams | Apache Kafka |
| :--- | :--- | :--- | :--- |
| **Delivery Guarantee** | At-most-once (Fire-and-forget) | At-least-once (ACKs & Consumer Groups) | At-least-once / Exactly-once |
| **Persistence** | None (100% ephemeral in-memory) | In-Memory with RDB/AOF persistence | Distributed Disk Log |
| **Backpressure** | None (Drops slow clients) | Built-in via stream offsets | Built-in via consumer pull model |
| **Memory Footprint** | Extremely low (zero storage) | Moderate (retained in RAM) | High (JVM + OS Page Cache) |
| **Ideal For** | Live cursor tracking, typing indicators | Real-time chat with recent history | Audit trails, analytics, high-retention persistence |

---

### 👨‍🏫 Interviewer Probe Questions

#### Probe 1: "What happens if a user is disconnected for 5 seconds (e.g., driving through a tunnel)? Does Redis Pub/Sub backfill their missed messages?"
> **Answer:** No. Redis Pub/Sub is purely ephemeral fire-and-forget. If the client socket is closed, the message is lost for that user. To support reconnects:
> 1. Messages are asynchronously written to a persistent datastore (PostgreSQL/Cassandra) or a buffered stream (Redis Streams/Kafka).
> 2. When the client reconnects, it sends its `last_read_message_id`.
> 3. The server fetches messages from the database where `id > last_read_message_id` while simultaneously attaching to the real-time WebSocket feed.

#### Probe 2: "How do you prevent a slow WebSocket client from causing high memory consumption on your Node.js/Go gateway server?"
> **Answer:** Implement **Backpressure**:
> * Monitor the WebSocket's outbound buffer size (in Node.js: `ws.bufferedAmount`).
> * If `ws.bufferedAmount` exceeds a threshold (e.g., 1MB), pause reading incoming frames from Redis for that client or disconnect the client if it falls too far behind.
> * Never let unbounded Redis messages accumulate in the Node.js event loop heap.

#### Probe 3: "If 100,000 users are in a single room (like a celebrity live stream), what breaks first in this architecture?"
> **Answer:** **The WebSocket Gateway's Egress Bandwidth and CPU.**
> * If 1 message is published, the gateway hosting 50,000 of those users must serialize and write 50,000 TCP packets.
> * **Mitigations:** 
>   1. **Throttling/Sampling:** Drop typing indicators and aggregate/batch chat messages at the gateway before sending down the wire (e.g., push 1 batch frame every 100ms instead of 50 individual frames).
>   2. **Tiered Fan-out:** Use a tree-structured fan-out layer or client-side sampling to prevent socket saturation.

---

### 4. ✅ Summary Cheat Sheet

* **3 Key Takeaways:**
  1. **WebSockets maintain state; Redis Pub/Sub abstracts state:** Gateways hold the persistent TCP connections to clients; Redis connects the isolated gateways.
  2. **Multiplex locally:** Never open one Redis connection per client. Use a single Redis subscriber per gateway server and map channels to sockets locally in memory.
  3. **Pub/Sub is ephemeral:** Redis Pub/Sub does not store data on disk or buffer for offline users. Always pair it with persistent storage or streams for message history.

* **⭐ The Golden Rule:**
  > *"Use Redis Pub/Sub for sub-millisecond ephemeral routing across server nodes, but never rely on it as a message queue or persistent store."*