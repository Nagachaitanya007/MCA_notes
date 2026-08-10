---
title: Webhook Security Architecture: HMAC Signing, Key Rotation, and Replay Protection
date: 2026-08-10T10:32:00.428220
---

# Webhook Security Architecture: HMAC Signing, Key Rotation, and Replay Protection

1. 💡 The "Big Picture" (Plain English):
       - What is this in simple terms?
       - Use a real-world analogy (e.g., a restaurant, a library, a bank).
       - Why should I care? What problem does it solve for me today?

2. 🛠️ How it Works (Step-by-Step):
       - Break down the process into simple steps (1, 2, 3...).
       - Show a clean, well-commented code snippet.
       - Use a Mermaid diagram or ASCII art to show the flow.

3. 🧠 The "Deep Dive" (For the Interview):
       - Now, explain the technical 'magic' (Internals, JVM, Database locking, etc.).
       - What are the trade-offs? (e.g. "It's faster, but uses more memory").
       - Explain 2-3 "Interviewer Probe" questions (how they ask this in a tricky way).

4. ✅ Summary Cheat Sheet:
       - 3 Key Takeaways.
       - 1 "Golden Rule" to remember for this topic.

---

### 1. 💡 The "Big Picture" (Plain English)

#### What is this in simple terms?
When your system dispatches webhooks over the open internet to a customer's server, anyone could potentially send fake HTTP POST requests to that customer and pretend to be you. **Webhook Security** ensures three critical guarantees:
1. **Authenticity:** The customer knows the payload *definitely* came from your notification system.
2. **Integrity:** The customer knows the payload *was not modified* in transit by a middleman.
3. **Non-Replayability:** An attacker cannot capture a past request and re-send it later to trick the customer's database.

#### Real-World Analogy
Imagine a royal messenger delivering an official decree from a King to a Duke. 
* To prove authenticity and integrity, the King stamps the wax on the envelope with his **unique signet ring** (HMAC Signature).
* To prevent someone from stealing an old royal decree and re-delivering it next month to trigger an action twice, the King **dates the parchment** inside. The Duke rejects any decree older than 5 minutes.

#### Why should I care?
Without request signing and replay prevention:
* A hacker could send a fake `payment_succeeded` webhook to your customer's endpoint, causing them to fulfill an order that was never paid for.
* A malicious actor could capture a legitimate `user_deleted` webhook off the wire and replay it continuously to exhaust downstream API servers.

---

### 2. 🛠️ How it Works (Step-by-Step)

#### The End-to-End Execution Flow

```
[ Kafka Event Topic ] 
       │
       ▼
[ SQS Outbound Queue ]
       │ (Buffers payload: tenant_id, payload_json, timestamp)
       ▼
[ Notification Delivery Worker ]
       │
       ├── 1. Fetch Tenant Signing Secret (from Redis/L1 Cache)
       ├── 2. Create Canonical String: `${timestamp}.${payload_json}`
       ├── 3. Calculate HMAC-SHA256 digest using Secret Key
       └── 4. Append Header: "X-Signature-256: t=1710000000,v1=a8f3b..."
       │
       ▼ (HTTP POST)
[ Customer Webhook Endpoint ]
       │
       ├── 1. Parse 't' (timestamp) & 'v1' (signature) from Header
       ├── 2. Verify timestamp is within tolerance window (e.g., < 5 mins)
       ├── 3. Recompute HMAC-SHA256 locally using shared Secret Key
       └── 4. Perform Constant-Time Byte Comparison (Prevent Timing Attacks)
```

#### Step-by-Step Security Pipeline

1. **Secret Generation:** When a customer registers a webhook endpoint, you generate a cryptographically strong secret key (e.g., `whsec_abc123...`) and display it to them **once**.
2. **Payload Canonicalization:** Before dispatching from the worker, construct a canonical string joining the current Unix timestamp and the raw JSON string: `1710000000.{"event":"order.created"}`.
3. **HMAC Calculation:** Compute a `HMAC-SHA256` hash using the customer's secret key and the canonical string.
4. **Header Formatting:** Attach a custom signature header modeled after industry standards (e.g., Stripe/GitHub format): `X-Signature-256: t=1710000000,v1=9f8a...`.
5. **Customer Verification:** The customer extracts the timestamp, validates freshness, reconstructs the canonical string, re-hashes it, and performs a timing-safe equality check.

#### Clean Node.js / TypeScript Example (Worker Delivery Side)

```typescript
import crypto from 'crypto';
import axios from 'axios';

interface WebhookPayload {
  tenantId: string;
  endpointUrl: string;
  body: Record<string, any>;
}

export async function signAndDispatchWebhook(
  payload: WebhookPayload,
  signingSecret: string
): Promise<void> {
  const timestamp = Math.floor(Date.now() / 1000);
  const rawBody = JSON.stringify(payload.body);

  // 1. Construct the Canonical String (Timestamp + Payload)
  // Joining timestamp prevents replay attacks; raw JSON prevents ordering tampering
  const canonicalPayload = `${timestamp}.${rawBody}`;

  // 2. Compute HMAC-SHA256 signature
  const hmac = crypto.createHmac('sha256', signingSecret);
  hmac.update(canonicalPayload, 'utf8');
  const signature = hmac.digest('hex');

  // 3. Construct standard signature header
  // Supports versioning (v1) and timestamp (t)
  const signatureHeader = `t=${timestamp},v1=${signature}`;

  // 4. Dispatch over HTTP POST
  await axios.post(payload.endpointUrl, rawBody, {
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'NotificationSystem-Worker/1.0',
      'X-Signature-256': signatureHeader,
    },
    timeout: 5000,
  });
}
```

---

### 3. 🧠 The "Deep Dive" (For the Interview)

#### Cryptographic Internals: Why HMAC-SHA256?
* **HMAC (Hash-based Message Authentication Code)** combines a cryptographic hash function (SHA-256) with a secret key. Simple concatenation (`sha256(secret + payload)`) is vulnerable to **Length Extension Attacks** (where an attacker can append data to the payload without knowing the secret). HMAC guards against this via nested hashing: $HMAC(K, m) = H((K' \oplus opad) \parallel H((K' \oplus ipad) \parallel m))$.
* **Canonicalization Pitfall:** JSON serialization isn't deterministic across frameworks. `{"a":1,"b":2}` vs `{"b":2,"a":1}` yields completely different hashes. Always sign the exact **raw string buffer** emitted to the wire, never re-serialize parsed objects downstream.

#### Preventing Side-Channel Timing Attacks
On the recipient side, string comparisons like `sigA === sigB` fail short-circuit evaluation: the engine returns `false` as soon as the first non-matching byte is found. An attacker measuring microsecond delivery latencies can guess the hash byte-by-byte. 
* **Fix:** Use constant-time byte comparisons (`crypto.timingSafeEqual()` in Node, `hmac.Equal()` in Go) which take the same execution time regardless of where the mismatch occurs.

#### Zero-Downtime Secret Rotation Strategy
When a customer rotates their secret key, in-flight webhooks in your Kafka -> SQS pipeline must not fail.
* **Dual-Signing Protocol:** During a secret key rotation window, store two active keys for the tenant: `primary_secret` and `next_secret` (or `old_secret`).
* Format header with multiple signatures: `X-Signature-256: t=1710000000,v1=sig_from_primary,v1=sig_from_old`.
* The customer accepts the webhook if **either** signature matches their current key.

```
+-----------------------------------------------------------------------+
| Signature Header Format (Dual Signing Window)                         |
| X-Signature-256: t=1710000000,v1=8a3f... (New Key),v1=1c2b... (Old)   |
+-----------------------------------------------------------------------+
```

#### Performance & Caching Trade-offs
1. **Secret Lookup Latency:** Looking up secrets in SQL/DynamoDB per dispatched webhook destroys delivery throughput (e.g., 50,000 SQS messages/sec).
   * **Solution:** Cache secrets in Redis or worker-local LRU memory with a 60-second TTL. 
   * **Trade-off:** Revoking a secret takes up to 60 seconds to propagate across all SQS workers.
2. **CPU Exhaustion via Large Payloads:** Computing HMAC-SHA256 over 10MB payload blobs consumes CPU cycles inside worker nodes.
   * **Solution:** Enforce maximum payload size bounds (e.g., 256KB) at the Kafka producer ingest level.

---

#### 🚩 Interviewer Probes & Tricky Questions

##### 1. "How do you handle secret key rotation without dropping webhooks currently buffered in SQS?"
> **Answer:** "We implement a dual-signing pattern. When a tenant requests key rotation, we mark the old secret as `retiring` with a 24-hour expiration and immediately provision a new `active` secret. When SQS workers process a payload, they retrieve both secrets from cache and emit a dual-signature header (`v1=new_sig,v1=old_sig`). The recipient's library iterates through the signatures. Once the window expires, the old secret is purged."

##### 2. "If an attacker intercepts a valid HTTPS POST request payload and header, how do you stop them from replaying it against the customer's server 10 minutes later?"
> **Answer:** "HTTPS protects the payload in transit, but if the customer's receiver exposes a public IP without authentication, a compromised downstream proxy could capture and replay it. We solve this by embedding a timestamp `t=` into the HMAC signature payload. The customer verifies that `|current_time - t| < 300 seconds`. An attacker replaying the exact headers 10 minutes later will be rejected because the timestamp signature is stale, and they cannot update `t` without invalidating `v1` because `t` is bound inside the HMAC calculation string (`t.payload`)."

##### 3. "Why not just use a simple API Token in the Authorization header instead of signing payloads with HMAC?"
> **Answer:** "A static API token proves *Identity* (who sent it), but it does not guarantee *Integrity* or *Non-Repudiation* of the payload itself. If a malicious proxy or buggy middlebox modifies the JSON payload in transit, a static API token still passes authentication. HMAC binds the exact payload content, timestamp, and identity together into a single immutable cryptographic signature."

---

### 4. ✅ Summary Cheat Sheet

#### 3 Key Takeaways
1. **Never sign raw objects after JSON re-parsing:** Sign the exact raw byte array/string dispatched on the HTTP wire to prevent property-ordering hashing bugs.
2. **Bind Timestamp to Signature:** Always include `t=` inside the HMAC canonical input string to mitigate replay attacks without requiring downstream database state.
3. **Use Timing-Safe Comparisons:** Compare calculated HMACs with incoming request signatures using constant-time evaluation functions to avoid timing side-channel exploits.

#### 💡 The Golden Rule
> **"Authenticate the Sender, Bind the Timestamp, Hash the Exact Raw Payload."**  
> *(Identity + Replay Prevention + Integrity = Complete Webhook Security).*