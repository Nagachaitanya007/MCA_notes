---
title: State Sync and Message Routing in Multi-Node WebSocket Systems
date: 2026-06-06T10:31:45.697361
---

# State Sync and Message Routing in Multi-Node WebSocket Systems

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine you are building a chat application like WhatsApp or Slack. When a single server runs your app, everything is easy: all connected users are on that same server. If Alice wants to message Bob, the server looks up Bob's active connection and pushes the message to him.

But what happens when your app grows, and you have to run **multiple servers**? 
* Alice connects to **Server 1**.
* Bob connects to **Server 2**.
* Alice sends a message to Bob. **Server 1** receives the message but has no idea who Bob is because Bob's connection lives in the memory of **Server 2**.

This is the **Cross-Node Routing Problem**. **WebSockets and Redis Pub/Sub** act as the bridge to solve this.

---

### The Real-World Analogy
Think of the chat system like a **large hotel chain**:
* **Guests (Users)** stay in different rooms across two different hotel towers (**Server 1** and **Server 2**).
* **Alice** is in Tower 1; **Bob** is in Tower 2.
* Alice wants to send a letter to Bob instantly. She hands it to the front desk clerk in Tower 1. 
* The clerk in Tower 1 cannot walk over to Tower 2 to deliver it. Instead, they drop the message into a **high-speed pneumatic tube system (Redis Pub/Sub)** that connects all front desks. 
* The tube delivers the message to the desk in Tower 2. The Tower 2 clerk reads the slip, sees that Bob is registered in their tower, and rings his room to deliver the letter.

---

### Why should I care?
Without this architecture, you cannot scale real-time systems horizontally. If you simply spin up multiple server instances behind a standard load balancer, your users will randomly connect to different nodes and find themselves trapped in "connectivity silos"—unable to exchange messages with anyone connected to a different server. 

---

## 2. 🛠️ How it Works (Step-by-Step)

### The Architectural Flow

```text
 [ Alice ]                                                     [ Bob ]
     │                                                            ▲
     │ 1. Send Message via WS                                     │ 5. Push Message via WS
     ▼                                                            │
┌───────────┐      2. Publish to Room Channel      ┌───────────┐  │
│  Server 1 │ ───────────────────────────────────> │  Redis    │  │
│ (Node A)  │ <─────────────────────────────────── │  Pub/Sub  │  │
└───────────┘    3. Broadcast to all subscribers   └───────────┘  │
                                                         │        │
                                                         │ 4. Dispatch
                                                         ▼        │
                                                   ┌───────────┐  │
                                                   │  Server 2 │ ─┘
                                                   │ (Node B)  │
                                                   └───────────┘
```

### The Step-by-Step Execution
1. **Connection & Subscription**: Alice connects to Server 1. Bob connects to Server 2. Both servers maintain local in-memory mappings of their connected clients (e.g., `userId -> socket`).
2. **Redis Channel Binding**: When Alice and Bob join a shared Chat Room (e.g., `room:engineering`), both Server 1 and Server 2 subscribe to the Redis channel `room:engineering`.
3. **Inbound Message**: Alice sends a message payload to Server 1: `{"room": "engineering", "text": "Hello!"}`.
4. **Publishing**: Server 1 intercepts this message and publishes it directly to the Redis channel `room:engineering`.
5. **Distribution**: Redis instantly replicates and pushes the message to all servers subscribed to `room:engineering` (Server 1 and Server 2).
6. **Local Dispatch**: 
   * Server 1 receives it from Redis, checks its local connection map, and sees Alice is local. It can skip sending it back to Alice (or use it as an ACK).
   * Server 2 receives it from Redis, checks its local connection map, finds Bob, and pushes the message down Bob's open WebSocket connection.

---

### Production-Grade Code Snippet (Node.js & Redis)

This clean TypeScript/JavaScript example showcases how to handle the WebSocket lifecycle alongside Redis Pub/Sub multiplexing.

```typescript
import { WebSocketServer, WebSocket } from 'ws';
import Redis from 'ioredis';

const PORT = process.env.PORT || 8080;
const wss = new WebSocketServer({ port: Number(PORT) });

// Redis Clients: One for publishing, one for subscribing (Redis requires dedicated subscription connections)
const pubClient = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const subClient = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

// Local registry of connected users on THIS server instance
// Map<userId, WebSocket>
const localConnections = new Map<string, WebSocket>();

// Track which channels this server instance is currently subscribed to in Redis
const activeSubscriptions = new Set<string>();

// 1. Subscribe to Redis Channels dynamically
async function subscribeToChannel(channel: string) {
  if (!activeSubscriptions.has(channel)) {
    activeSubscriptions.add(channel);
    await subClient.subscribe(channel);
    console.log(`Node subscribed to Redis Channel: ${channel}`);
  }
}

// 2. Listen for messages arriving from Redis (The cross-node communication hub)
subClient.on('message', (channel, messageStr) => {
  const payload = JSON.parse(messageStr);
  const { senderId, targetRoom, text } = payload;

  console.log(`Redis Msg received on [${channel}]: From ${senderId}`);

  // Broadcast to all locally connected users in this room
  // (In a real system, you would track which user is in which room locally)
  for (const [userId, socket] of localConnections.entries()) {
    if (socket.readyState === WebSocket.OPEN) {
      // Send the payload to the actual client
      socket.send(JSON.stringify({ room: targetRoom, senderId, text }));
    }
  }
});

// 3. Handle incoming WebSocket connections
wss.on('connection', (socket: WebSocket, req) => {
  // Simple extraction of userId from query parameters (e.g., ws://localhost:8080?userId=alice)
  const url = new URL(req.url || '', `http://${req.headers.host}`);
  const userId = url.searchParams.get('userId');

  if (!userId) {
    socket.close(4001, 'Unauthorized: userId required');
    return;
  }

  // Register user connection locally
  localConnections.set(userId, socket);
  console.log(`User [${userId}] connected locally to port ${PORT}`);

  // Automatically subscribe this node to a default global/shared channel
  subscribeToChannel('room:lobby');

  // Handle incoming messages from the client
  socket.on('message', async (rawData) => {
    try {
      const data = JSON.parse(rawData.toString());
      const { room, text } = data; // e.g., { room: "room:lobby", text: "Hi!" }

      const messagePayload = JSON.stringify({
        senderId: userId,
        targetRoom: room,
        text: text,
        timestamp: Date.now()
      });

      // Instead of distributing locally, publish to Redis. 
      // Redis will route it to ALL nodes (including this one).
      await pubClient.publish(room, messagePayload);

    } catch (err) {
      socket.send(JSON.stringify({ error: 'Invalid payload format' }));
    }
  });

  // Handle client disconnection
  socket.on('close', () => {
    localConnections.delete(userId);
    console.log(`User [${userId}] disconnected from port ${PORT}`);
    
    // Cleanup subscriptions if no users are left (Optional optimization)
    if (localConnections.size === 0) {
       // In production, unsubscribe from rooms that have no active local participants
    }
  });
});

console.log(`WebSocket Server started on port ${PORT}`);
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic & System Limits

#### 1. "At-Most-Once" Delivery Dilemma
Redis Pub/Sub is **fire-and-forget**. It does not persist messages. If Server 2 loses its connection to Redis for 5 seconds, or if Bob's phone briefly goes through a tunnel and drops its TCP connection, any message sent during that window is **lost forever** in the ether. 

* **The Fix**: 
  * Do not use Redis Pub/Sub as the primary system of record. 
  * When a message arrives at Server 1, write it to a persistent datastore (e.g., PostgreSQL, MongoDB, or Redis Streams) **before** or concurrently with publishing to Redis Pub/Sub.
  * When Bob's client reconnects, it must send a `sync` request with the last message ID it successfully received, allowing the server to fetch missing messages from the database.

#### 2. Subscription Scalability & Memory Footprint
If you have 1,000,000 active users, and you subscribe to a unique channel per user (e.g., `user:active:userId`) to route private direct messages, your Redis instance will have 1,000,000 active subscriptions. 
* Each subscription in Redis consumes memory to track client references. At massive scale, this can consume gigabytes of RAM purely for routing metadata.
* **The Optimization (Multiplexing)**: Instead of one Redis subscription per user, subscribe each Server Node to a *single* node-specific channel (e.g., `node:server-instance-99`). When sending a message to Bob, the system queries a shared cache (like Redis Hash) to locate Bob's node placement: `Bob -> server-instance-99`. The message is then published strictly to `node:server-instance-99`. This reduces the Redis subscription count from $N$ (number of users) to $M$ (number of server instances).

#### 3. Backpressure and Socket Buffer Bloat
If Bob is on a slow 3G connection, but Alice is spamming high-resolution images or messages, Server 2 will receive messages from Redis faster than it can write them to Bob's TCP socket. The memory on Server 2 will inflate as it buffers these messages in the Node.js event loop queue, leading to Out-Of-Memory (OOM) crashes.

* **The Fix**: Implement a connection-level buffer monitor. If the buffered amount of data on a WebSocket exceeds a threshold (e.g., `socket.bufferedAmount > 1MB`), pause reading from the Redis subscription feed for that specific user or gracefully terminate the connection to protect the node.

---

### Trade-Off Matrix: Messaging Backbones

| Metric | Redis Pub/Sub | Redis Streams / Kafka | WebRTC (P2P) |
| :--- | :--- | :--- | :--- |
| **Latency** | Ultra-low (<2ms) | Low (5-20ms) | Absolute lowest (Direct) |
| **Persistence** | None (In-memory) | High (Disk/Log-based) | None |
| **Delivery Guarantee**| At-Most-Once | At-Least-Once | Best-effort |
| **Scale Bottleneck** | Max Redis Memory/Network | Disk I/O & Partitioning | NAT traversal / Signaling |

---

### Interviewer Probe Questions

#### 1. *"What happens if Server 2 crashes while a message is in flight inside Redis?"*
> **Answer**: Because Redis Pub/Sub is fire-and-forget, that message will be lost to any client connected to Server 2. To build a resilient system, we should assign every message a monotonically increasing sequence ID (Snowflake ID) and persist it to an asynchronous database queue (or Redis Stream) upon receipt. When the client reconnects to a healthy server (say, Server 3), it requests delta recovery: *"Give me all messages for Room X starting from sequence ID 10045."*

#### 2. *"If we scale to 100,000 group chat rooms, does every server need to subscribe to all 100,000 Redis channels?"*
> **Answer**: No. This is a common scalability anti-pattern. If every server subscribes to every channel, you are performing a **N-squared broadcast**, defeating the purpose of scaling out. 
> 
> Instead, we should implement **Dynamic Subscription Management**: a server node should only subscribe to a Redis room channel if it has at least one locally connected client in that room. When the last local client leaves the room or disconnects, the server immediately sends an `UNSUBSCRIBE` command to Redis for that room channel. This keeps the active subscription count on any single node strictly bound to the active users on that specific node.

#### 3. *"How do you handle message ordering guarantees across multiple nodes?"*
> **Answer**: Network latency and distributed clocks mean physical timestamps (`Date.now()`) cannot be trusted for strict ordering. 
> 
> We must generate a logical sequence number per chat room. This can be achieved by using a Redis counter (`INCR room:123:seq`) as the single source of truth for ordering. Each message must acquire its sequence number from this counter before distribution. When clients render the chat, they sort messages purely by this sequence ID rather than their local arrival time.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **WebSockets are Stateful, Redis is Stateless**: WebSockets anchor a client to a single, physical server. Redis Pub/Sub is the decoupled layer that enables these siloed servers to route messages to one another in sub-milliseconds.
2. **Beware the "Fire-and-Forget" Nature**: Redis Pub/Sub does not store data. If a connection breaks, messages vanish. Always back your real-time channel with a persistent data store or stream for reliable message retrieval.
3. **Keep Subscriptions Lean**: Dynamically subscribe/unsubscribe your server nodes to Redis channels based on local user presence to prevent your Redis instance from running out of memory.

---

### 1 "Golden Rule"
> **"Never assume a message delivered to a WebSocket server has reached the client. Always design for connection loss with message persistence, unique sequence IDs, and client-driven delta sync on reconnection."**