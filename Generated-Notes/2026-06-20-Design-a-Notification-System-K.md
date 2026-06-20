---
title: Multi-Tenant Fair-Share Scheduling in a Kafka-to-SQS Notification System
date: 2026-06-20T10:31:56.273109
---

# Multi-Tenant Fair-Share Scheduling in a Kafka-to-SQS Notification System

## 1. 💡 The "Big Picture" (Plain English)

### What is this in simple terms?
Imagine an airport security checkpoint. If a massive tour bus containing 500 passengers arrives all at once, the airport doesn't close all security lanes to process only that bus while single travelers miss their flights. Instead, they open multiple lanes and distribute travelers so that individual passengers can still get through quickly.

In a notification system, **Multi-Tenant Fair-Share Scheduling** is our airport security plan. It ensures that if one massive customer (Tenant A) suddenly triggers 10 million marketing push notifications, it won't block or delay a single, critical Multi-Factor Authentication (MFA) passcode notification sent by another customer (Tenant B).

```
[Spammy Tenant A] ──(10,000,000 Notifications)──┐
                                                ├──► [ Our Fair-Share System ] ──► [Tenant B processed instantly]
[Urgent Tenant B] ──(1 Single MFA Code)─────────┘
```

### Why should I care?
If you build a standard notification pipeline (e.g., a simple FIFO queue), a single high-volume client can hog the entire system. This is called **Queue Starvation**. 

If Tenant B's transactional emails or SMS alerts lag by 45 minutes because Tenant A is blasting holiday promo webhooks, Tenant B will churn, your system will violate its SLAs (Service Level Agreements), and your business will lose money. 

---

## 2. 🛠️ How it Works (Step-by-Step)

To build a high-throughput, fair-share notification system, we combine the strengths of **Kafka** (for high-volume ingestion and log storage) and **AWS SQS** (for lightweight, concurrent buffering with per-tenant message grouping).

```
   +------------------+      +------------------+      +------------------+
   |   API Gateway    | ---> |   Kafka Topic    | ---> | Router Service   |
   | (Ingests Events) |      | (Ingest Buffer)  |      | (Polls Kafka)    |
   +------------------+      +------------------+      +------------------+
                                                                |
                                                                v
   +------------------+      +------------------+      +------------------+
   | Webhook/SMS/Push | <--- |   Worker Pool    | <--- |   AWS SQS FIFO   |
   |   Destinations   |      | (Fair Consuming) |      |  (MessageGroupId |
   +------------------+      +------------------+      |  = tenant_id)    |
                                                       +------------------+
```

### The Step-by-Step Flow:
1. **Ingest**: Users hit your API Gateway. The gateway writes the events directly to a high-throughput **Kafka Ingestion Topic**.
2. **Route**: A lightweight **Router Service** polls Kafka. Instead of executing the notification directly, it routes the message to an **AWS SQS FIFO Queue**.
3. **Isolate**: When pushing to SQS, the Router sets the SQS `MessageGroupId` to the `tenant_id`. 
4. **Consume**: A pool of Worker nodes pulls messages from SQS. Because of the `MessageGroupId` configuration, SQS distributes messages across workers such that no single `MessageGroupId` (tenant) can block workers from picking up messages from other groups.

### Code Implementation (TypeScript Router)

Here is how the **Router Service** consumes from Kafka and publishes to SQS with dynamic, tenant-fair grouping.

```typescript
import { Kafka } from 'kafkajs';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';

const kafka = new Kafka({ brokers: ['localhost:9092'] });
const sqs = new SQSClient({ region: 'us-east-1' });

const consumer = kafka.consumer({ groupId: 'notification-router-group' });
const SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/NotificationQueue.fifo';

interface NotificationEvent {
  tenantId: string;
  recipient: string;
  channel: 'email' | 'sms' | 'webhook';
  payload: Record<string, any>;
  timestamp: string;
}

async function startRouter() {
  await consumer.connect();
  await consumer.subscribe({ topic: 'incoming-notifications', fromBeginning: true });

  await consumer.run({
    eachMessage: async ({ message }) => {
      if (!message.value) return;
      
      const event: NotificationEvent = JSON.parse(message.value.toString());
      
      // Construct the SQS payload with fair-share properties
      const sqsParams = new SendMessageCommand({
        QueueUrl: SQS_QUEUE_URL,
        MessageBody: JSON.stringify(event),
        // CRITICAL: MessageGroupId isolates processing per tenant.
        // SQS FIFO guarantees order within a group, but processes different groups in parallel.
        MessageGroupId: event.tenantId,
        // Deduplication ID ensures we don't send duplicate notifications within a 5-minute window
        MessageDeduplicationId: `${event.tenantId}:${event.timestamp}:${event.recipient}`
      });

      try {
        await sqs.send(sqsParams);
        console.log(`Routed event for Tenant: ${event.tenantId} to SQS.`);
      } catch (err) {
        console.error(`Failed to route event for Tenant ${event.tenantId}:`, err);
        // Implement dead-letter-queue (DLQ) or retry logic here
      }
    },
  });
}

startRouter().catch(console.error);
```

---

## 3. 🧠 The "Deep Dive" (For the Interview)

### The Technical Magic: SQS FIFO `MessageGroupId` Mechanics
Under the hood, SQS FIFO (First-In-First-Out) queues handle fair-share distribution natively using the `MessageGroupId`. 

* **The Rule of Message Groups**: SQS guarantees that messages belonging to the same `MessageGroupId` are processed in strict chronological order.
* **The Parallelism Secret**: SQS allows multiple workers to consume from a single FIFO queue concurrently. If Worker A picks up a message for `MessageGroupId: Tenant-1`, SQS locks *only* that group. Worker B can concurrently pull messages from the same queue, and SQS will hand it messages from `MessageGroupId: Tenant-2`.
* **The Fair-Share Outcome**: If Tenant 1 dumps 1,000,000 messages into the queue, they will all share the same `MessageGroupId`. A single worker (or a subset of workers) will chew through them. Meanwhile, if Tenant 2 sends 1 message, it bypasses the queue backlog because its `MessageGroupId` is free, instantly routeing to an available idle worker.

```
Queue State: [T1, T1, T1, T1, T1, T2, T1, T1]
Worker 1: Processing T1 (Locks Group T1)
Worker 2: Polls queue -> Receives T2 immediately (Bypasses locked T1 messages!)
```

---

### Trade-offs: Kafka vs. SQS FIFO

| Metric | Kafka (Ingestion Layer) | SQS FIFO (Distribution Layer) |
| :--- | :--- | :--- |
| **Throughput** | Ultra-high (Millions of events/sec via partitioning). | Limited (Maximum 300 msg/sec, or 3,000 msg/sec with high-throughput batching). |
| **Ordering** | Guaranteed per-partition. If Partition Key = Tenant ID, high-volume tenants create hot partitions, stalling consumer groups. | Guaranteed per `MessageGroupId`. No partition scaling limits to manage manually. |
| **Dynamic Scaling** | Requires manual or auto-scaled re-partitioning (heavy operational cost). | Serverless. Scaled automatically by AWS. |

**The Architectural Compromise**: 
We use **Kafka** as our shock-absorber at the front door because it can handle unexpected traffic spikes without breaking a sweat. We then stream from Kafka into **SQS FIFO** to gain transactional isolation and fair-share delivery.

---

### Interviewer Probe Questions (How to Ace Them)

#### 1. "If SQS FIFO has a throughput limit of 3,000 messages/sec, how do you handle scale if your overall system needs to process 50,000 notifications/sec?"
* **Your Answer**: "We implement **Queue Sharding**. Instead of sending all tenants to a single SQS FIFO queue, we deploy a pool of SQS queues (e.g., 20 queues). When routing a message, we hash the `tenant_id` to assign them to a specific SQS queue (e.g., `Queue_Hash(tenant_id) % 20`). This multiplies our throughput limit by the number of shards (20 queues × 3,000 msg/s = 60,000 msg/s) while maintaining strict ordering and fair-share mechanics within each shard."

#### 2. "What happens if a tenant's downstream webhook endpoint is extremely slow or down? Won't their message group block your workers?"
* **Your Answer**: "Yes, if Tenant A's webhook server is down and throwing 503s, our worker will keep retrying, which locks their `MessageGroupId` and stalls their specific pipeline. To prevent this from consuming our global worker pool, we implement a **Circuit Breaker** and a **DLQ (Dead Letter Queue)** strategy. If a tenant's failures exceed a threshold, we route their notifications to a dedicated 'Slow/Retry Queue' or a Tenant-specific DLQ, freeing up primary SQS FIFO workers to handle healthy tenants."

---

## 4. ✅ Summary Cheat Sheet

### 3 Key Takeaways
1. **Never use tenant IDs as Partition Keys in Kafka** for end-to-end processing. A massive tenant will create a "hot partition," stalling consumers for other tenants sharing that partition.
2. **Decouple high-throughput ingestion from fair delivery**. Use Kafka to absorb the massive load write-bursts, and use SQS FIFO to schedule deliveries fairly.
3. **Leverage `MessageGroupId`**. It is the easiest, cloud-native way to achieve concurrent processing across different clients while keeping transactions strictly ordered per client.

### 1 Golden Rule to Remember
> *"Optimize your system so that a slow customer only slows down themselves, never your other customers."*