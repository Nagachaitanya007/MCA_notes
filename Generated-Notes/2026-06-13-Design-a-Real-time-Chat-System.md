---
title: Cross-Server Message Delivery Pipeline in Distributed WebSocket Chat
date: 2026-06-13T10:31:55.625784
---

# Cross-Server Message Delivery Pipeline in Distributed WebSocket Chat

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
Imagine you and your friend are using a chat app. You are connected to Server A, and your friend is connected to Server B. When you send a message, Server A needs a way to instantly forward that message to Server B so your friend can see it. 

A **Cross-Server Message Delivery Pipeline** is the digital highway that routes messages between different chat servers in real-time, ensuring that no matter which server a user is connected to, they receive their messages instantly.

#### A Real-World Analogy
Think of a large hotel with two separate towers:
* **Tower 1** has its own front desk (Server A). **Alice** is staying in Tower 1.
* **Tower 2** has its own front desk (Server B). **Bob** is staying in Tower 2.

```
       [ Tower 1 ]                         [ Tower 2 ]
     Alice (Room 101)                    Bob (Room 202)
            │                                   ▲
            ▼                                   │
      [ Front Desk A ] ◄───[ Intercom ]────► [ Front Desk B ]
```

If Alice wants to send a note to Bob:
1. She hands the note to **Front Desk A**.
2. Front Desk A doesn't know where Bob is staying (they only manage Tower 1 rooms).
3. Instead of searching every room, Front Desk A broadcasts over the **hotel-wide intercom** (Redis Pub/Sub): *"Message for Bob!"*
4. **Front Desk B** hears this announcement, checks their guest book, sees Bob is in Room 202, and slips the note under his door.

#### Why should I care?
By default, WebSocket connections are **stateful** and tied to a single, specific server memory space. If your application grows and you need to scale out to 2, 10, or 100 servers, users connected to different servers won't be able to talk to each other. 

Using **Redis Pub/Sub** as a message broker solves this. It acts as the shared nervous system connecting all your isolated WebSocket servers, enabling real-time communication at scale.

---

### 2. 🛠️ How it Works (Step-by-Step)

#### The Workflow
1. **The Handshake**: Client A establishes a persistent TCP WebSocket connection with Server 1. Client B connects to Server 2.
2. **The Subscription**: Both Server 1 and Server 2 subscribe to a global Redis Pub/Sub channel (e.g., `chat:messages`).
3. **The Outbound Message**: Client A sends a message targeting Client B to Server 1.
4. **The Broadcast**: Server 1 wraps the message with metadata and publishes it to the Redis channel.
5. **The Delivery**: Redis broadcasts the message to all subscribed servers. Server 2 receives it, looks up Client B in its active connection registry, and pushes the message down Client B's open socket.

```mermaid
sequenceDiagram
    autonumber
    actor Alice as Client A (on Server 1)
    participant S1 as WebSocket Server 1
    participant Redis as Redis Pub/Sub
    participant S2 as WebSocket Server 2
    actor Bob as Client B (on Server 2)

    Alice->>S1: Send Message: { to: "Bob", text: "Hi" }
    Note over S1: S1 checks local connections.<br/>Bob is not here!
    S1->>Redis: PUBLISH chat_channel { to: "Bob", msg: "Hi" }
    Note over Redis: Redis broadcasts to all<br/>subscribed servers
    Redis->>S1: Message Received (Discarded; Bob not local)
    Redis->>S2: Message Received (Processed)
    Note over S2: S2 checks local connections.<br/>Bob is here!
    S2->>Bob: Send via WebSocket: "Hi"
```

#### Code Implementation (Node.js & Redis)

Below is a production-ready pattern showing how a WebSocket server handles incoming connections, registers local clients, and routes messages using Redis Pub/Sub.

```javascript
const WebSocket = require('ws');
const Redis = require('ioredis');

// 1. Initialize Redis clients (We need separate connections for Pub and Sub)
const pubClient = new Redis({ host: '127.0.0.1', port: 6379 });
const subClient = new Redis({ host: '127.0.0.1', port: 6379 });

const PORT = process.env.PORT || 8080;
const wss = new WebSocket.Server({ port: PORT });

// Local memory registry to keep track of clients connected to THIS specific server
const localConnections = new Map(); // Map<UserId, WebSocketInstance>

console.log(`WebSocket server running on port ${PORT}`);

// 2. Subscribe to the global Redis channel
const REDIS_CHANNEL = 'global_chat_routing';
subClient.subscribe(REDIS_CHANNEL, (err) => {
  if (err) console.error("Failed to subscribe to Redis Pub/Sub", err);
});

// 3. Handle messages coming from other servers via Redis
subClient.on('message', (channel, incomingRaw) => {
  if (channel !== REDIS_CHANNEL) return;

  try {
    const payload = JSON.parse(incomingRaw);
    const { targetUserId, message, senderId } = payload;

    // Check if the recipient is connected to THIS server instance
    const targetSocket = localConnections.get(targetUserId);
    if (targetSocket && targetSocket.readyState === WebSocket.OPEN) {
      targetSocket.send(JSON.stringify({ from: senderId, text: message }));
    }
  } catch (error) {
    console.error("Error processing Redis message payload", error);
  }
});

// 4. Handle client connections to this server
wss.on('connection', (ws, req) => {
  // Extract user ID from query parameters (e.g., ws://localhost:8080?userId=Alice)
  const urlParams = new URLSearchParams(req.url.split('?')[1]);
  const userId = urlParams.get('userId');

  if (!userId) {
    ws.close(4000, "Missing userId parameter");
    return;
  }

  // Register client locally
  localConnections.set(userId, ws);
  console.log(`User [${userId}] connected to server on port ${PORT}`);

  // Handle incoming messages from the WebSocket client
  ws.on('message', async (messageData) => {
    try {
      const parsedData = JSON.parse(messageData);
      const { to, text } = parsedData;

      const payload = {
        targetUserId: to,
        senderId: userId,
        message: text
      };

      // Publish message globally to Redis so the server holding "to" can deliver it
      await pubClient.publish(REDIS_CHANNEL, JSON.stringify(payload));
    } catch (err) {
      ws.send(JSON.stringify({ error: "Invalid payload format" }));
    }
  });

  // Handle client disconnection
  ws.on('close', () => {
    localConnections.delete(userId);
    console.log(`User [${userId}] disconnected`);
  });
});
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### The Internal Mechanics of Redis Pub/Sub
Redis handles Pub/Sub with an $O(1)$ time complexity for message publishing. When a message is published, Redis reads its subscription table—which maps channel names to arrays of connected client file descriptors—and writes the data to those TCP sockets.

However, **Redis Pub/Sub is completely stateless and "fire-and-forget".**
* It does not persist messages to disk.
* It does not maintain any queue.
* If a WebSocket server drops its connection to Redis for even half a second, all messages sent during that window are permanently lost.

#### Architectural Trade-offs: Channel Granularity

When designing the routing topology in Redis, you have two primary options:

| Strategy | Design | Pros | Cons |
| :--- | :--- | :--- | :--- |
| **Single Shared Channel** | All servers subscribe to a single channel `chat_global`. | Very simple to implement. Low memory overhead on Redis. | Every server must parse every message, discarding those for non-local users (High CPU waste at scale). |
| **Channel-Per-User** | Every server subscribes to specific channels for its active local users (e.g., `user:101`). | High efficiency; servers only receive messages destined for their connected clients. | High memory footprint on Redis due to managing millions of ephemeral channels and subscriptions. |

*Recommendation for Interviews*: For high-scale systems, use a **Consistent Hashing ring** or **User-Room mapping database** (like DynamoDB or Cassandra) combined with targeted Redis Pub/Sub channels to balance CPU overhead and Redis memory consumption.

---

#### Interviewer Probe Questions (and how to answer them)

##### Probe 1: "What happens if a user's network connection is unstable and they reconnect every few seconds? How do you prevent message loss?"
* **The Trap**: Saying "Redis Pub/Sub will queue them up." (It won't).
* **The Answer**: 
  "To handle unstable connections without message loss, we must decouple delivery from storage. 
  1. When Server 1 receives a message, it writes it to a persistent database (e.g., MongoDB, PostgreSQL, or Cassandra) and generates a unique, sequential Snowflake ID.
  2. The message is then published over Redis Pub/Sub.
  3. If the recipient is disconnected, the WebSocket push fails.
  4. Upon reconnection, the client sends a `sync` frame containing the last message ID they successfully acknowledged. The server queries the database for all messages where `id > last_acknowledged_id` and backfills them over the socket."

##### Probe 2: "What happens if a slow consumer (a client on a weak 3G network) cannot read messages as fast as they are being pushed?"
* **The Trap**: Assuming the browser handles it automatically.
* **The Answer**: 
  "This creates a **backpressure** problem on the server. If a client consumes messages slower than they arrive, the server's outbound TCP buffer fills up. The server framework (like Node.js or Go) will start buffering these frames in application memory. Under heavy load, this will cause the server to crash with an Out-of-Memory (OOM) error.
  To prevent this:
  1. Monitor the socket write buffer size (e.g., `ws.bufferedAmount` in WebSockets).
  2. If the buffer exceeds a specific threshold, pause reading from the incoming queue for that user.
  3. If the buffer continues to grow, force-disconnect the client (kill the TCP connection) and let them perform a standard reconnection backfill when their network recovers."

##### Probe 3: "If we scale to 10 million concurrent users, how do we prevent Redis from becoming the single point of failure (SPOF) and bottleneck?"
* **The Trap**: Suggesting a single, larger Redis instance (vertical scaling).
* **The Answer**: 
  "At 10 million users, a single Redis instance will bottle-neck on CPU usage since Redis is single-threaded. We must shard our Pub/Sub layer. 
  Instead of one Redis instance, we use a cluster of Redis nodes. We shard the subscription channels across the cluster using a hashing function on the `roomId` or `userId`. For example, channel `room:9421` always maps to Redis Node 3. This distributes the Pub/Sub CPU load linearly across multiple nodes."

---

### 4. ✅ Summary Cheat Sheet

```
   [ Client A ]                      [ Client B ]
        │                                 ▲
        │  1. Send Frame                  │  4. Push Frame
        ▼                                 │
  [ Server 1 ] ── 2. Publish ──► [ Redis ] ── 3. Broadcast ──► [ Server 2 ]
```

#### 3 Key Takeaways
1. **WebSockets are Stateful, Redis is Stateless**: WebSockets hold physical TCP connections on specific servers. Redis Pub/Sub acts as the bus that connects these isolated servers together.
2. **Pub/Sub is Fire-and-Forget**: Do not rely on Redis Pub/Sub for message history or delivery guarantees. Use a persistent database as the source of truth for message logs.
3. **Beware of Backpressure**: Always monitor socket write-buffers on your servers to prevent a slow client from consuming all server memory.

#### 1 Golden Rule to Remember
> *"Never trust the connection state. Design your real-time system as if every client is on the verge of disconnecting, and use database-backed sequence IDs to synchronize state upon reconnection."*