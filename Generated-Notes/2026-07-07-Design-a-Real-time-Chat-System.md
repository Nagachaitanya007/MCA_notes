---
title: Message Delivery Guarantees and Offline Buffering in Distributed WebSocket Systems
date: 2026-07-07T10:32:47.779716
---

# Message Delivery Guarantees and Offline Buffering in Distributed WebSocket Systems

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine you are texting a friend. When your friend is driving through a mountain tunnel with no cell service, what happens to the messages you send? They shouldn't vanish into thin air, nor should your phone crash trying to send them. 

In a real-time chat system, **WebSockets** act like an open phone call (constant, live connection), while **Redis Pub/Sub** acts like an internal PA system, routing messages between different chat servers. 

But what happens when a user's phone goes offline, or their app closes? Redis Pub/Sub is "fire-and-forget"—if the user isn't actively connected to the server at that exact millisecond, the message is lost forever. **Message Delivery Guarantees and Offline Buffering** is the architecture we build *around* WebSockets and Redis to make sure every single message is safely delivered, stored, and acknowledged, no matter how bad the user's internet connection is.

### The Real-World Analogy: Registered Mail vs. Standard Post
* **Standard Post (Fire-and-Forget):** You drop a letter in a mailbox. You *hope* it gets there, but if the recipient moved or is on vacation, you have no way of knowing, and the letter might get thrown away. This is raw Redis Pub/Sub.
* **Registered Mail (Application-Level ACKs):** You mail a package. The mailman delivers it, but the recipient must physically sign a receipt (an **Acknowledgment** or **ACK**). If they aren't home, the post office holds the package in a secure depot (an **Offline Buffer**/Database) and leaves a note. Only when the recipient signs the receipt is the delivery marked as complete.

### Why should I care?
Without these mechanisms, your chat app will constantly drop messages when users switch from Wi-Fi to cellular data, enter elevators, or background their apps. Users will lose trust in your platform instantly. Designing this correctly prevents message duplication, minimizes database bottlenecking, and keeps your system highly responsive.

---

## 2. 🛠️ How it Works (Step-by-Step)

To guarantee message delivery without losing performance, we use a **hybrid approach**:
1. **Durable Writes First:** Every message is saved to a persistent database (with a state of `PENDING`) before it is broadcast.
2. **Transient Routing:** Redis Pub/Sub routes the live message to the server holding the recipient's active connection.
3. **Application-Level ACKs:** The client must send back an explicit "I received this" signal over the WebSocket.
4. **Fallback to Push Notifications / Offline Storage:** If no ACK is received within a timeout period, the server stops attempting live delivery and sends a mobile Push Notification instead.

### The Delivery Pipeline

```
 [Sender Client]
       │
       │ (1) WS: Send Message
       ▼
 [WebSocket Server A] ──(2) Write to DB (Status: PENDING) ──► [Durable Database]
       │
       │ (3) Publish to Channel: "user_userB"
       ▼
 ╔═══════════════════╗
 ║  Redis Pub/Sub    ║
 ╚═══════════════════╝
       │
       │ (4) Deliver to subscriber
       ▼
 [WebSocket Server B]
       │
       │ (5) WS: Push Message to User B
       ▼
 [Receiver Client]
       │
       │ (6) WS: Send App-Level ACK {"msg_id": 999}
       ▼
 [WebSocket Server B] ──(7) Async Update DB (Status: DELIVERED) ──► [Durable Database]
```

### The Implementation: Connection Manager & ACK Tracker

Here is a clean Node.js/TypeScript implementation showing how a server handles message delivery, awaits an application-level ACK, and triggers an offline fallback if the ACK is missed.

```typescript
import { WebSocket } from 'ws';
import { EventEmitter } from 'events';

interface ChatMessage {
  id: string;
  senderId: string;
  receiverId: string;
  content: string;
  timestamp: number;
}

class DeliveryCoordinator {
  // Map to track active WebSocket connections per User ID
  private activeConnections = new Map<string, WebSocket>();
  // Event emitter to handle asynchronous ACKs from clients
  private ackEmitter = new EventEmitter();
  private readonly ACK_TIMEOUT_MS = 5000;

  constructor() {
    // Listen for incoming ACK messages globally on this server instance
    this.ackEmitter.on('ack_received', (messageId: string, userId: string) => {
      console.log(`[ACK] Message ${messageId} confirmed by user ${userId}`);
    });
  }

  /**
   * Register a new active WebSocket connection
   */
  public registerConnection(userId: string, socket: WebSocket) {
    this.activeConnections.set(userId, socket);

    socket.on('message', (rawPayload: string) => {
      try {
        const payload = JSON.parse(rawPayload);
        if (payload.type === 'ACK') {
          // Trigger the event to resolve the pending delivery promise
          this.ackEmitter.emit('ack_received', payload.messageId, userId);
        }
      } catch (err) {
        console.error('Failed to parse incoming WS message:', err);
      }
    });

    socket.on('close', () => {
      this.activeConnections.delete(userId);
    });
  }

  /**
   * Orchestrates the delivery of a message with At-Least-Once guarantees
   */
  public async deliverMessage(message: ChatMessage): Promise<boolean> {
    const recipientSocket = this.activeConnections.get(message.receiverId);

    // 1. If recipient is offline on this node, immediately trigger fallback
    if (!recipientSocket || recipientSocket.readyState !== WebSocket.OPEN) {
      this.triggerOfflineFallback(message);
      return false;
    }

    // 2. Deliver the message over the WebSocket
    recipientSocket.send(JSON.stringify({ type: 'NEW_MESSAGE', data: message }));

    try {
      // 3. Race against a timeout waiting for the Application-level ACK
      await this.waitForAck(message.id, message.receiverId);
      
      // 4. Update state in database to 'DELIVERED'
      await this.updateMessageStateInDB(message.id, 'DELIVERED');
      return true;
    } catch (error) {
      console.warn(`[Delivery Failed] No ACK for message ${message.id}. Falling back.`);
      this.triggerOfflineFallback(message);
      return false;
    }
  }

  /**
   * Returns a promise that resolves when the client sends an ACK, or rejects on timeout
   */
  private waitForAck(messageId: string, userId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timeoutId);
        this.ackEmitter.off('ack_received', ackListener);
      };

      const ackListener = (receivedId: string, sendingUser: string) => {
        if (receivedId === messageId && sendingUser === userId) {
          cleanup();
          resolve();
        }
      };

      // Set up timeout rejection
      const timeoutId = setTimeout(() => {
        cleanup();
        reject(new Error('ACK timeout exceeded'));
      }, this.ACK_TIMEOUT_MS);

      // Register listener for the incoming ACK event
      this.ackEmitter.on('ack_received', ackListener);
    });
  }

  private async updateMessageStateInDB(messageId: string, status: 'PENDING' | 'DELIVERED') {
    // In production, write asynchronously to PostgreSQL or MongoDB
    console.log(`[Database] Message ${messageId} status updated to: ${status}`);
  }

  private triggerOfflineFallback(message: ChatMessage) {
    // In production, this would trigger an Apple Push Notification (APNS) or Google Firebase (FCM) push
    console.log(`[Push Notification] Sent notification to ${message.receiverId} for message: "${message.content}"`);
  }
}
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Hidden Trap: Why TCP ACKs Are Not Enough
A common mistake candidates make in system design interviews is assuming that because WebSockets run over **TCP**, and TCP guarantees packet delivery, we do not need application-level ACKs. 

**This is a critical error.**
1. **The OS Buffer Lie:** A TCP ACK only means the recipient's *operating system kernel* received the IP packet. It does **not** mean the application runtime (e.g., the browser's JavaScript event loop) successfully processed, parsed, or rendered the message. If the browser tab crashes or the phone battery dies immediately after the OS gets the packet but before the web app processes it, the message is lost forever.
2. **Proxies & Load Balancers:** Your WebSocket connection passes through intermediate reverse proxies (like Nginx, AWS ALBs, or Cloudflare). A TCP ACK might be returned to your server by the proxy, even if the proxy's connection down-stream to the client is broken or currently reconnecting.

**Conclusion:** You *must* implement application-level ACKs for high-fidelity chat applications.

---

### Managing Backpressure in WebSocket Connections
In real-world scenarios, a server can push messages to a client much faster than the client’s network can download them. This disparity causes **Backpressure**.

When a WebSocket server writes a message to a client, the message is stored in an in-memory buffer within the server process until the TCP socket can send it. If a client has a highly degraded network connection (high packet loss), this memory buffer grows.

If you have 50,000 active connections on a single server, and 10% of them are on slow networks receiving a high volume of group messages, your server will quickly run out of memory (OOM crash) due to these accumulating outbound buffers.

#### How to mitigate Backpressure:
* **Buffer Checking:** Check the WebSocket's `bufferedAmount` property (in Node.js/browser) before sending more messages.
* **Rate-limiting and Disconnection:** If a client's write buffer exceeds a threshold (e.g., 1MB), disconnect them. Let them reconnect and fetch missed messages from the database sequentially, rather than choking the server's memory.

---

### Trade-offs: At-Least-Once vs. At-Most-Once Delivery

| Strategy | Delivery Guarantee | Overhead & Complexity | Best Used For |
| :--- | :--- | :--- | :--- |
| **At-Most-Once** (Fire-and-forget) | 0% to 99.9% (Best effort). Duplicates impossible, but loss expected. | Low. Zero ACK tracking state or DB overhead. | Typing indicators, user presence updates (online/offline). |
| **At-Least-Once** (With App ACKs) | 100% guarantee of delivery. However, duplicates can occur on network timeouts. | High. Requires DB updates, retry logic, timeout timers, and client deduping. | Standard text messages, financial transactions, read receipts. |

---

### Interviewer Probes (The Tricky Questions)

#### Probe 1: "If the user is offline, why not just write messages to Redis Pub/Sub anyway and let them catch up later?"
* **Answer:** Redis Pub/Sub is inherently **stateless and ephemeral**. If a client is not actively subscribed to a channel at the precise moment a message is published, that message is discarded by Redis instantly. Redis does not buffer messages for disconnected subscribers. To handle offline catch-up, we must bypass Pub/Sub entirely for offline users and write directly to a durable store (like Cassandra, ScyllaDB, or MongoDB), which the client queries on reconnection.

#### Probe 2: "How do you handle the 'Thundering Herd' problem when 20,000 devices reconnect simultaneously after a brief cellular tower outage?"
* **Answer:** When 20,000 devices reconnect, they will all try to:
  1. Establish a new TLS handshake and WebSocket connection.
  2. Request missed messages since their last known sequence ID.
  
  This will crush the database and memory. To prevent this:
  * **Exponential Backoff with Jitter:** Clients must not reconnect immediately. They must use randomized reconnect delays (e.g., $1s \pm 200ms$, then $2s \pm 400ms$).
  * **Sequence-Based Delta Sync:** The client sends its last received `sequence_id` (or timestamp). Instead of a heavy relational query, the server performs a highly optimized, indexed query using a composite key (e.g., `WHERE receiver_id = X AND sequence_id > Y`) with strict pagination limits.
  * **Connection Throttling (Rate Limiting):** Use an API Gateway or reverse proxy (e.g., Envoy, Nginx) to rate-limit incoming WebSocket connections per second, gracefully rejecting excess attempts with status code `429` or closing connections with custom WS close codes.

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **TCP is Not Enough:** Always use application-level ACKs to confirm that the recipient's UI actually received and processed a message, not just the device's operating system.
2. **Decouple Live and Offline Flows:** Use Redis Pub/Sub only for routing messages to *actively connected* servers. If a user is offline, skip Pub/Sub, save the message to your durable database, and trigger a push notification.
3. **Guard Server Memory:** Monitor WebSocket backpressure on your servers (`bufferedAmount`). Forcefully disconnect clients that cannot drain their TCP send buffers fast enough to protect the host machine from running Out Of Memory (OOM).

### 💡 The Golden Rule
> **"Write to disk before you send over the wire."**
> To prevent message loss under any circumstance, a message must be safely committed to your database in a pending state *before* you publish it to Redis or attempt to send it down a live WebSocket.