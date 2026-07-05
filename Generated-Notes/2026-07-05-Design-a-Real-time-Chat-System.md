---
title: Distributed Session Registry and Pub/Sub Topology for Real-Time Chat
date: 2026-07-05T10:31:53.250404
---

# Distributed Session Registry and Pub/Sub Topology for Real-Time Chat

### 💡 The "Big Picture" (Plain English)

Imagine you are staying at a massive, multi-tower luxury hotel (the **Chat System**). 

You are in Tower A (Server A), and your friend is in Tower B (Server B). If your friend wants to send you a letter in real-time:
1. They can't just throw it out the window; they don't know which room or even which tower you are in.
2. They give the letter to the front desk of Tower A.
3. Tower A looks up a central guest book (**Session Registry**) to see: *"Where is Bob staying?"* 
4. The guest book says: *"Bob is in Tower B, Room 502."*
5. Tower A sends the letter through an underground pneumatic tube system (**Redis Pub/Sub**) directly to Tower B.
6. Tower B receives it and slides it under your door (your open **WebSocket Connection**).

```
   [ Alice ]                                                      [ Bob ]
       │                                                             ▲
       │ 1. "Hi Bob"                                                 │ 5. Push via
       ▼                                                             │    WebSocket
┌──────────────┐      2. Lookup Bob's Server      ┌──────────────┐   │
│   Server A   │ ───────────────────────────────> │    Redis     │ ──┘
│ (WebSocket)  │ <─────────────────────────────── │  (Registry)  │
└──────────────┘      3. Bob is on Server B       └──────────────┘
       │                                                 ▲
       │                                                 │
       │ 4. Publish to "server:B" channel                │ (Same Redis
       └─────────────────────────────────────────────────┘  Cluster)
```

#### Why should you care?
HTTP is a **pull-based** protocol (the client must ask the server for updates). WebSockets are **push-based** (the server can send data to the client instantly). 

However, WebSocket connections are **stateful** and pinned to a single server memory space. If your application grows and you need to scale horizontally to 5 or 10 servers, Server A has no direct way of talking to a client connected to Server B. This pattern solves the multi-node routing problem, making your real-time architecture horizontally scalable.

---

### 🛠️ How it Works (Step-by-Step)

#### The Routing & Delivery Pipeline:
1. **Establish & Register:** A client connects to a WebSocket server. The server registers this connection in a centralized, fast-lookup database (Redis) mapping `userId -> serverId`.
2. **Subscribe:** The WebSocket server subscribes to a dedicated channel in Redis corresponding to its own `serverId` (e.g., `channel:server_B`).
3. **Dispatch:** When Server A receives a message from Client A destined for Client B, it queries Redis to find Client B's server ID.
4. **Publish:** Server A publishes the payload to Client B's server channel on Redis Pub/Sub.
5. **Consume & Push:** Server B receives the message from the Pub/Sub subscription, finds the local WebSocket connection socket for Client B in its local memory, and pushes the raw frame.

#### Clean Node.js / TypeScript Implementation:

```typescript
import { WebSocketServer, WebSocket } from 'ws';
import Redis from 'ioredis';

const PORT = Number(process.env.PORT) || 8080;
const SERVER_ID = `server:${PORT}`;

// Redis clients: Pub/Sub requires dedicated connections
const redisClient = new Redis(); // For general commands (GET/SET)
const redisPub = new Redis();    // For publishing messages
const redisSub = new Redis();    // For subscribing to server-specific messages

// Local map of active WebSocket connections on THIS server instance
const localConnections = new Map<string, WebSocket>();

const wss = new WebSocketServer({ port: PORT });

// 1. Subscribe to this specific server's channel
redisSub.subscribe(SERVER_ID, (err) => {
  if (err) console.error(`Failed to subscribe to ${SERVER_ID}`, err);
  else console.log(`Subscribed to Pub/Sub channel: ${SERVER_ID}`);
});

// 2. Listen for messages routed via Redis Pub/Sub from other servers
redisSub.on('message', (channel, message) => {
  if (channel === SERVER_ID) {
    const { to, content, from } = JSON.parse(message);
    const targetSocket = localConnections.get(to);
    
    // If the user is still connected to this server, push the message
    if (targetSocket && targetSocket.readyState === WebSocket.OPEN) {
      targetSocket.send(JSON.stringify({ from, content }));
    }
  }
});

wss.on('connection', async (ws: WebSocket, req) => {
  // Assume authentication middleware sets this header
  const userId = req.headers['user-id'] as string; 
  if (!userId) {
    ws.close(4001, 'Unauthorized');
    return;
  }

  // Register session globally and locally
  localConnections.set(userId, ws);
  await redisClient.set(`presence:${userId}`, SERVER_ID, 'EX', 3600); // 1-hour TTL

  console.log(`User ${userId} connected to ${SERVER_ID}`);

  ws.on('message', async (rawData) => {
    try {
      const { to, content } = JSON.parse(rawData.toString());

      // Find where the recipient is located
      const targetServerId = await redisClient.get(`presence:${to}`);

      if (!targetServerId) {
        // Handle offline scenario (e.g., save to DB as unread)
        ws.send(JSON.stringify({ system: `${to} is offline. Message saved.` }));
        return;
      }

      // Route the message to the target server via Pub/Sub
      const payload = JSON.stringify({ from: userId, to, content });
      await redisPub.publish(targetServerId, payload);

    } catch (err) {
      ws.send(JSON.stringify({ error: 'Invalid frame format' }));
    }
  });

  ws.on('close', async () => {
    localConnections.delete(userId);
    // Clean up registry if the entry still points to this server
    const currentRegistry = await redisClient.get(`presence:${userId}`);
    if (currentRegistry === SERVER_ID) {
      await redisClient.del(`presence:${userId}`);
    }
    console.log(`User ${userId} disconnected from ${SERVER_ID}`);
  });
});
```

---

### 🧠 The "Deep Dive" (For the Interview)

#### 1. The Bottleneck of User-Specific vs. Server-Specific Pub/Sub Channels
A naive design creates a Redis Pub/Sub channel for every user (e.g., `user:alice`). 
* **The Problem:** If you have 10 million concurrent users, Redis has to manage 10 million subscription channels. This wrecks Redis's memory allocation and search space overhead.
* **The Solution:** Use **Server-Specific Channels** (`server:server_A`). Since you only have a few dozen/hundred server nodes, Redis only has to manage a tiny handful of channels. The servers act as demultiplexers: they receive the coarse server-level feed and route the packet to the exact local socket in $O(1)$ time using an in-memory `Map`.

#### 2. Managing "Ghost Sessions" and Ephemeral State
If a server node crashes instantly (e.g., an OOM error or hardware failure), the `close` event handler on WebSockets **will not fire**. 
* **The Danger:** The Redis Presence Registry will still map thousands of users to `server:dead_node`. Messages sent to those users will be routed to a black hole.
* **The Mitigation:** 
  1. **Heartbeats (Ping/Pong):** The WebSocket servers must periodically ping clients. If a client doesn't pong within a window (e.g., 30s), close the socket and clean up Redis.
  2. **Presence TTL & Keep-Alives:** The presence keys in Redis must have a Short TTL (e.g., 60 seconds). Active WebSocket servers must periodically issue a `pipeline` of `EXPIRE` commands to keep their active local users alive in Redis.
  3. **Node Orphans Cleanup:** Introduce a cluster manager (like Consul or ZooKeeper) or use Redis Sentinel to track server health. When a node is marked dead, a script should sweep and delete all keys matching `presence:*` pointing to that dead server.

```
[ Active WebSocket ] ──(Every 30s Heartbeat)──> [ Updates Redis TTL ]
[ Crashed WebSocket ] ──(No Heartbeat)─────────> [ Redis Keys Auto-Expire (TTL) ]
```

#### 3. Trade-offs of Redis Pub/Sub
* **Pros:** Ultra-low latency (sub-millisecond), highly performant, dynamic subscription patterns.
* **Cons:** **At-Most-Once Delivery.** If Server B's Redis client briefly loses connection to the Redis Cluster while a message is published, that message is lost forever. It does not queue messages for offline subscribers.
* **Mitigation:** If your SLA requires **At-Least-Once Delivery**, you must swap Redis Pub/Sub for **Redis Streams** or **Apache Kafka**, combined with a delivery acknowledgement flow (Application-level ACKs) between clients.

---

### 💡 Interviewer Probes: Tricky Questions & How to Answer

#### Probe 1: "What happens if a user opens three browser tabs? How does your routing logic handle multiple concurrent connections for the same user ID?"
* **The Trait They Are Testing:** System completeness and handling of realistic user edge cases.
* **Your Answer:** 
  > "If a user opens multiple tabs, we can change our Redis session mapping from a string key-value pair to a **Redis Hash** or a **Set** of connection descriptors (e.g., `user:123 -> { connectionId1: server_A, connectionId2: server_B }`). When routing, we fetch all active destinations for that user and publish to all involved servers. On the client-side, each tab generates or receives a distinct connection ID to prevent duplicate message handling errors."

#### Probe 2: "How do you handle 'Hot-spotting' in Redis Pub/Sub when a celebrity with 5 million followers sends a message?"
* **The Trait They Are Testing:** Understanding of distributed bottleneck thresholds.
* **Your Answer:** 
  > "If a celebrity sends a message to 5 million followers, writing to Redis 5 million times to lookup targets and publishing 5 million individual messages will crash the system. To scale this, we decouple the write/delivery pipeline:
  > 1. We immediately push the fan-out task to a background queue (like Celery, BullMQ, or Kafka).
  > 2. The queue workers batch lookups and group recipient servers together.
  > 3. Instead of sending 5,000 separate messages to 5000 users on Server B, we publish a **single batched message** to `server:B` containing the payload and a list of target user IDs. Server B's CPU then handles the local iteration and socket pushes."

---

### ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **WebSockets are Stateful, Redis is Stateless:** You cannot scale WebSockets horizontally without a centralized state manager (Registry) and a routing fabric (Pub/Sub) to bridge the gap between isolated servers.
2. **Server-Level Subscriptions Scale Better:** Do not create a Redis Pub/Sub channel per user. Create a channel **per server instance** to keep Redis's memory and performance profile clean and fast.
3. **Handle Silent Server Deaths:** State is ephemeral. Always pair your Session Registry with short TTLs and periodic heartbeats to avoid "ghost connections" routing messages to dead servers.

#### 1 Golden Rule
> *"Never trust the client to disconnect cleanly; always design your state registry to heal itself through TTL-based heartbeats."*