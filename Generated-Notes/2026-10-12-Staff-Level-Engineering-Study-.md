---
title: Staff-Level Engineering Study Guide: Integrating Gemini/LLM APIs into Java Systems
date: 2026-10-12T04:31:56.933757
---

# Staff-Level Engineering Study Guide: Integrating Gemini/LLM APIs into Java Systems

---

## 1. 🧱 The Core Concept (Basics Refresh)

Integrating LLM APIs (such as Google Gemini, OpenAI, or Anthropic) into Java enterprise ecosystems differs fundamentally from standard REST/RPC integrations. The primary divergence lies in **latency profiles**, **payload dynamics**, and **connection lifecycles**:

*   **OLTP RPCs:** 5–50ms execution times, bounded small payloads, deterministic failure modes.
*   **LLM Inference RPCs:** 500ms–30,000ms execution times, indeterminate response lengths, streaming token delivery (chunked Transfer-Encoding / Server-Sent Events), token-budget constraints, and nondeterministic payloads.

```
+-------------+         HTTP/2 Multiplexed / gRPC           +--------------------+
|  Java App   | -------------------------------------------> | Gemini Gateway     |
| (Loom/Netty)| <------------------------------------------- | (Vertex AI / REST) |
+-------------+   SSE / Chunked Frames (Token Streaming)     +--------------------+
       |
       +--> Local Tokenizer (JNI/BPE) -> In-Memory Context Truncation
       +--> Jackson Streaming Parser  -> Zero-Copy Tool Call Deserialization
```

### Integration Planes

1.  **Protocol Bindings:**
    *   **gRPC (Vertex AI Engine):** Multiplexed HTTP/2 transport over binary Protobuf. Optimal for throughput, payload compression, and bidirectional streaming. Uses persistent Netty channels under the hood.
    *   **REST/SSE (`https://generativelanguage.googleapis.com`):** Standard HTTP/1.1 or HTTP/2 transport with `text/event-stream` payloads for Server-Sent Events (SSE). Simplifies perimeter proxying and dynamic edge routing.

2.  **SDK Layer vs. Raw Transport:**
    *   *Google Cloud Vertex AI Java SDK (`com.google.cloud:google-cloud-vertexai`):* Heavyweight, gRPC-backed, tied to GCP IAM and service accounts. Enforces strict protobuf schemas.
    *   *LangChain4j / Spring AI:* High-level declarative abstractions. Excellent for rapid orchestration, but abstracts away connection pooling, backpressure mechanics, and GC allocations.
    *   *Raw Reactive/Loom HTTP Clients (`java.net.http.HttpClient`, Netty, Reactor-Netty):* Highest throughput, deterministic thread profiling, minimal memory footprint. Essential for low-latency, high-concurrency API gateways.

3.  **Token Mechanics & Context Windows:**
    *   **Context Budgets:** Input prompt + dynamic history + system instructions + tool definitions $\le \text{Context Window}$ (e.g., 1M–2M tokens for Gemini 1.5 Pro).
    *   **Tokenization Disparity:** 1 token $\approx$ 0.75 English words. Java chars are UTF-16 ($2\text{ bytes}$ standard, up to $4\text{ bytes}$ for surrogate pairs). Memory calculation for raw context:
      $$\text{Heap Allocation} \approx \text{Tokens} \times 4 \text{ bytes (string representation)} \times 2\text{--}3 \times (\text{Jackson AST node overhead})$$
    *   *Never* use character count as a proxy for token limits. Use client-side tokenizers (via ONNX runtime / JNI bindings) or Google's `countTokens` endpoint before execution.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### 2.1 Concurrency Models: Virtual Threads (Loom) vs. Reactive (Reactor/Netty)

Because LLM invocations hold connections open for tens of seconds, your execution runtime model dictates system stability.

```
Thread-per-Core (Reactive/Netty):
[Event Loop Core 1] ---> [Channel 1 (Tokens)] -> Frame -> Parse -> Downstream Sink
                    ---> [Channel 2 (Idle)]   -> Yield

Thread-per-Task (Project Loom):
[Carrier Worker 1]  ===> [Virtual Thread A] (Parked on SocketRead0)
                    ===> [Virtual Thread B] (Active: Deserializing JSON AST)
```

#### Project Loom (JDK 21+ Virtual Threads)
*   **Mechanism:** When an HTTP client performs a blocking network read awaiting the next SSE token frame, the underlying `VirtualThread` unmounts from its carrier `ForkJoinWorkerThread`. The carrier is free to process other virtual threads.
*   **The Trap:** **Carrier Thread Pinning.** If code invokes LLM streaming inside a `synchronized` block or touches `JNI` boundaries (e.g., C++ tokenizers), the virtual thread is pinned to the carrier thread:
    ```java
    // DANGEROUS: Carrier thread pinned during long-lived LLM stream
    synchronized (mutex) {
        geminiClient.streamGenerateContent(prompt).forEach(this::processToken);
    }
    ```
    *Remedy:* Replace with `java.util.concurrent.locks.ReentrantLock`. Verify with `-Djdk.tracePinnedThreads=full`.

#### Reactive (Reactor / Netty / Spring WebFlux)
*   **Mechanism:** Non-blocking I/O multiplexed over an `Epoll` event loop. One thread handles thousands of open LLM SSE streams concurrently.
*   **The Trade-off:** Memory-efficient, but backpressure propagation through downstream consumers requires complex reactive pipeline composition (`Flux.create()`, `limitRate()`, `onBackpressureBuffer()`).

---

### 2.2 Network Architecture, HTTP/2 Multiplexing & Connection Pooling

LLM calls break traditional HTTP connection pool semantics (e.g., Apache `PoolingHttpClientConnectionManager` with defaults of 20 connections max per route).

1.  **HTTP/2 Multiplexing:**
    *   A single physical TCP socket handles multiple concurrent virtual streams.
    *   Gemini API endpoints support HTTP/2. A single connection can interleave dozens of SSE response streams via HTTP/2 `DATA` frames with distinct stream IDs.
    *   *Failure Mode:* **TCP Head-of-Line Blocking.** If packet loss occurs on an underlying TCP socket multiplexing 100 concurrent LLM streams, *all 100 streams stall* until the missing segment is retransmitted.
    *   *Solution:* Cap streams per connection (e.g., Netty's `Http2FrameCodecBuilder.maxConcurrentStreams(100)`), and maintain a pool of multiplexed connections rather than a single multiplexed pipe.

2.  **Socket Timeouts & Idle States:**
    *   Standard HTTP clients default read timeouts to 5–10 seconds.
    *   **Time-To-First-Token (TTFT)** for large Gemini prompts (especially with deep context caching or extensive tool declarations) can exceed 5,000ms.
    *   You must decouple the **Read Timeout** (maximum interval between consecutive stream frames) from the **Connection/Execution Timeout** (maximum wall-clock time for the full response):
    ```java
    HttpClient client = HttpClient.newBuilder()
        .version(HttpClient.Version.HTTP_2)
        .connectTimeout(Duration.ofSeconds(10))
        .build();

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create("https://generativelanguage.googleapis.com/..."))
        .timeout(Duration.ofMinutes(2)) // Total request budget
        .build();
    ```

---

### 2.3 Streaming Ingestion, Backpressure, and Zero-Copy Deserialization

When processing Server-Sent Events (`text/event-stream`), naive string parsing introduces catastrophic GC pressure:

$$\text{Allocation Velocity} = \text{Requests/sec} \times \frac{\text{Tokens}}{\text{Request}} \times \text{JSON Overhead (~2KB/token object)}$$

For 500 concurrent users receiving 50 tokens/second, this can generate **>50 MB/sec of ephemeral string garbage**, triggering frequent JVM Young Gen collections (Stop-the-World pauses).

```
TCP Byte Stream
      │
      ▼
ByteBuf / ByteBuffer (Netty / JDK)
      │
      ▼
Jackson `JsonParser` (Non-blocking / Streaming Tokenizer)
      │  (Does NOT instantiate intermediate String or Tree Model)
      ▼
Direct Extract: `candidates[0].content.parts[0].text`
      │
      ▼
Target Buffer / WebSocket Outbound Queue
```

*Architectural Requirement:* Utilize **Jackson Streaming API (`JsonParser` via `JsonFactory`)** over `ObjectMapper#readTree` or standard data-binding. Inspect byte buffers directly, extract the `text` delta field, and forward it down the consumer pipe without deserializing the entire Gemini envelope (safety ratings, token counts, metadata).

---

### 2.4 Function Calling (Tool Use) Execution Loop

Tool calling transforms the LLM into a deterministic state machine.

```
       +---------------------------------------------+
       | Client prepares prompt + Tool Definitions   |
       +---------------------------------------------+
                              │
                              ▼
       +---------------------------------------------+
       | Gemini API: Emits `functionCall` token frame|
       +---------------------------------------------+
                              │
                              ▼
       +---------------------------------------------+
       | Java Application: Dispatches locally        |
       | Method Reflection / MethodHandle invocation |
       +---------------------------------------------+
                              │
                              ▼
       +---------------------------------------------+
       | Append `functionResponse` to History Array  |
       +---------------------------------------------+
                              │
                              ▼
       +---------------------------------------------+
       | Final Gemini API Request (Produces Text)    |
       +---------------------------------------------+
```

*Schema Generation Mechanics:* LLMs require tools defined in JSON Schema format. In Java, this involves generating the JSON schema using Jackson/Swagger introspectors over POJOs at startup, caching them in memory, and passing them inside the `tools` array payload. Dynamic schema generation at runtime is an anti-pattern due to excessive reflection overhead.

---

## 3. ⚠️ The Interview Warzone (Scenarios, Probing, and Solutions)

### Scenario 1: The Gateway GC Collapse Under SSE Streaming Load

#### The Situation
You built a Java-based API Gateway (Spring Boot 3, JDK 21) exposing an endpoint that streams Gemini responses to mobile clients using Server-Sent Events. Under load testing (2,000 concurrent streaming requests), response latency spikes exponentially, TTFT degrades to 15 seconds, and the JVM crashes with `java.lang.OutOfMemoryError: Java heap space`.

#### The Probing Questions
*   *Interviewer:* "Why did memory crash under low-throughput text streaming? It's just a few words per second."
*   *Interviewer:* "Show me where the threads are blocked and how your connection pool behaves under this workload."
*   *Interviewer:* "How does backpressure apply between the Google upstream server, your gateway, and a slow mobile client on 3G?"

#### The Systematic Breakdown

1.  **The Root Cause:**
    *   **Buffer Bloat:** Downstream mobile clients on slow networks read SSE events slower than Gemini emits them.
    *   If you use an unbounded queue or naive reactive stream (`Flux.map(...)`) without an explicit backpressure strategy, the gateway buffers unconsumed upstream tokens indefinitely in the JVM heap.
    *   **String Deserialization Churn:** Deserializing each SSE data frame into full POJOs via `ObjectMapper.readValue(chunk, GeminiResponse.class)` allocates millions of transient objects, retaining them in memory because slow clients delay consumer completion.

2.  **The End-to-End Architectural Solution:**
    *   Implement **reactive pull-through backpressure** or a bounded-buffer virtual thread pipeline.
    *   Utilize **Zero-Allocation Jackson Parsing** with netty byte-buffers.
    *   Terminate slow downstream consumers using drop strategies or absolute stream deadlines.

```java
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import java.io.InputStream;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

public class HighThroughputGeminiConsumer {
    private static final JsonFactory JSON_FACTORY = new JsonFactory();
    private final HttpClient httpClient;

    public HighThroughputGeminiConsumer(HttpClient httpClient) {
        this.httpClient = httpClient;
    }

    public void streamTokenDeltas(HttpRequest request, Consumer<String> downstreamConsumer) throws Exception {
        // Enforce strict upstream backpressure via a bounded queue
        final BlockingQueue<String> tokenQueue = new ArrayBlockingQueue<>(64);
        
        // Execute request handling stream as raw bytes to prevent intermediate String allocations
        HttpResponse<InputStream> response = httpClient.send(
            request, 
            HttpResponse.BodyHandlers.ofInputStream()
        );

        if (response.statusCode() != 200) {
            throw new RuntimeException("Upstream Error: " + response.statusCode());
        }

        // Spawn Virtual Thread dedicated to low-overhead streaming parse
        Thread.ofVirtual().name("gemini-parser").start(() -> {
            try (InputStream in = response.body();
                 JsonParser parser = JSON_FACTORY.createParser(in)) {
                 
                while (!parser.isClosed() && parser.nextToken() != null) {
                    // Match target payload path: candidates[0].content.parts[0].text
                    if (parser.currentToken() == JsonToken.FIELD_NAME && "text".equals(parser.currentName())) {
                        parser.nextToken(); // Advance to string literal
                        String delta = parser.getText();
                        
                        // Bounded push to queue: blocks parsing thread if consumer is slow
                        // Avoids heap exhaustion by pushing backpressure to TCP window
                        if (!tokenQueue.offer(delta, 10, TimeUnit.SECONDS)) {
                            throw new RuntimeException("Downstream consumer timed out. Dropping stream.");
                        }
                    }
                }
            } catch (Exception e) {
                // Signal stream termination with error
            } finally {
                // Sentinel value to notify termination
                tokenQueue.offer("[DONE]");
            }
        });

        // Downstream Consumption Loop
        while (true) {
            String token = tokenQueue.poll(30, TimeUnit.SECONDS);
            if (token == null || "[DONE]".equals(token)) {
                break;
            }
            downstreamConsumer.accept(token);
        }
    }
}
```

---

### Scenario 2: The Distributed Throttling & 429 Cascade (TPM/RPM Exhaustion)

#### The Situation
Your microservice cluster (50 nodes) interfaces with Gemini. Gemini limits you to 1,000,000 Tokens Per Minute (TPM) and 2,000 Requests Per Minute (RPM). During peak hours, nodes receive HTTP `429 Too Many Requests` (or gRPC `RESOURCE_EXHAUSTED`). In response, naive client retries flood the API, causing a thundering herd, cascading regional outages, and total starvation of real-time paths.

```
Incoming Burst ──┐
                 ├──> [Local Token Bucket (Node 1)] ──┐
Incoming Burst ──┘                                    │
                                                      ├──> [Redis Cluster: Central Token Pool]
Incoming Burst ──┐                                    │    (Atomic Dual Lua Script: RPM + TPM)
                 ├──> [Local Token Bucket (Node N)] ──┘               │
Incoming Burst ──┘                                                    ▼
                                                             Gemini Upstream API
```

#### The Probing Questions
*   *Interviewer:* "How do you rate limit across 50 nodes when you don't know the exact number of tokens a request will generate until Gemini completes it?"
*   *Interviewer:* "How does your retry policy prevent thundering herd across an elastic fleet?"
*   *Interviewer:* "Explain the latency cost of distributed coordination vs. local heuristics."

#### The Architectural Solution

1.  **Optimistic Token Pre-Allocation with Post-Inference Reconciliation:**
    *   *Step 1 (Pre-flight):* Estimate token usage:
      $$\text{Total Tokens} \approx \text{Local Count(Prompt)} + \text{Max Output Tokens Parameter}$$
    *   *Step 2 (Reservation):* Decrement the distributed bucket via a Redis Lua script. If rejected, wait or fail fast *prior* to network dispatch.
    *   *Step 3 (Post-flight):* Gemini returns exact metrics in `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`). Reconcile by refunding unused tokens to Redis:
      $$\text{Refund} = \text{Max Output Tokens} - \text{Actual Output Tokens}$$

2.  **Atomic Lua Script (Multi-Resource: RPM and TPM):**
    ```lua
    -- KEYS[1]: RPM Key, KEYS[2]: TPM Key
    -- ARGV[1]: Current Time, ARGV[2]: Max RPM, ARGV[3]: Max TPM, ARGV[4]: Reserved Tokens

    local current_rpm = redis.call('CL.THROTTLE', KEYS[1], ARGV[2], 60, 60, 1)
    if current_rpm[3] == -1 then
        return { -1, current_rpm[4] } -- Denied RPM
    end

    local current_tpm = redis.call('CL.THROTTLE', KEYS[2], ARGV[3], 60, 60, ARGV[4])
    if current_tpm[3] == -1 then
        -- Rollback RPM grant
        return { -2, current_tpm[4] } -- Denied TPM
    end

    return { 0, 0 } -- OK
    ```

3.  **Backoff with Full Jitter:**
    Standard exponential backoff synchronizes retries into devastating traffic spikes. Use **Exponential Backoff with Full Jitter** (Decorrelated Jitter):
    $$t_{\text{sleep}} = \min(t_{\text{max}}, \text{Uniform}(0, t_{\text{base}} \times 2^{\text{attempt}}))$$

```java
import java.time.Duration;
import java.util.concurrent.ThreadLocalRandom;

public class ResilientLLMInvoker {
    private static final int MAX_RETRIES = 4;
    private static final long BASE_DELAY_MS = 500;
    private static final long MAX_DELAY_MS = 8000;

    public <T> T invokeWithResilience(SupplierWithException<T> call) throws Exception {
        int attempt = 0;
        while (true) {
            try {
                return call.get();
            } catch (GeminiRateLimitException ex) { // Catches 429 / RESOURCE_EXHAUSTED
                attempt++;
                if (attempt > MAX_RETRIES) {
                    throw new SystemCapacityExceededException("Exhausted retries on upstream rate limits", ex);
                }

                // Parse standard Gemini Retry-After header if present
                long retryAfterMs = ex.getRetryAfterMillis();
                long backoff;
                
                if (retryAfterMs > 0) {
                    // Upstream explicitly requested a cool-off window; honor it with small jitter
                    backoff = retryAfterMs + ThreadLocalRandom.current().nextLong(50, 250);
                } else {
                    // Full Jitter calculation
                    long exponentialMax = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * (1L << attempt));
                    backoff = ThreadLocalRandom.current().nextLong(0, exponentialMax);
                }

                Thread.sleep(backoff);
            }
        }
    }

    @FunctionalInterface
    public interface SupplierWithException<T> {
        T get() throws Exception;
    }
}
```

---

### Scenario 3: Context Exhaustion, Stateful History, and Function Calling Loops

#### The Situation
You are implementing an interactive Multi-Turn Agent in Java utilizing Gemini Function Calling (Tools). Over a 20-minute conversation with continuous database inspection operations, users receive:
`INVALID_ARGUMENT: The input token count exceeds the maximum context length`.
Additionally, your JVM's memory footprint spikes due to chat session caching in local state.

#### The Probing Questions
*   *Interviewer:* "How do you manage conversation history in memory without creating stateful JVM monoliths that can't scale horizontally?"
*   *Interviewer:* "When the context window approaches its limits, how do you evict tokens without breaking dynamic Tool-Call chains?"
*   *Interviewer:* "What happens if a tool produces a 50,000-row JSON string? How do you prevent it from breaking the context budget?"

#### The Architectural Solution

1.  **The Tool Call Invariant Rule:**
    In both the Gemini and OpenAI execution models, **a `FunctionCall` part must be followed immediately by its corresponding `FunctionResponse` part**.
    *Catastrophic Bug:* If an eviction algorithm uses standard FIFO truncation and drops the `FunctionCall` while leaving the `FunctionResponse` in the history, the upstream API will reject the request with a non-recoverable schema error:
    ```
    Content with role 'function' must follow a content with role 'model' containing a function call.
    ```

```
[User Turn 1]  <-- Safe to evict
[Model Turn 1] <-- Safe to evict
-----------------------
[User Turn 2]
[Model: FunctionCall(readDb)] ──┐ MUST EVICT TOGETHER
[User: FunctionResponse(rows)] ─┘ OR PRESERVE TOGETHER
-----------------------
[Model: Final Answer]
```

2.  **Atomic Eviction Unit Strategy:**
    Define an atomic unit of history as a **Transaction Turn**:
    *   Type A: Simple (User Content $\leftrightarrow$ Model Content)
    *   Type B: Extended (User Content $\leftrightarrow$ Model Tool Call $\leftrightarrow$ Tool Result $\leftrightarrow$ Model Content)
    Eviction must operate strictly over complete **Transaction Turns**, never bare individual messages.

3.  **Context Condensation Pipeline:**
    When token counts approach the sliding window threshold:
    *   *Step 1:* Run summarization on older Transaction Turns via an asynchronous worker (`gemini-1.5-flash`), compressing 10,000 tokens into a 200-token summary node.
    *   *Step 2:* Pin the system prompt at Index 0.
    *   *Step 3:* Inject the summary node at Index 1.
    *   *Step 4:* Append sliding-window raw turns at the tail.

```java
import java.util.*;

public class ContextWindowManager {
    private final int maxTokenBudget;
    private final TokenCounter tokenCounter;

    public ContextWindowManager(int maxTokenBudget, TokenCounter tokenCounter) {
        this.maxTokenBudget = maxTokenBudget;
        this.tokenCounter = tokenCounter;
    }

    public List<Turn> pruneContext(List<Turn> fullHistory) {
        int currentTokens = tokenCounter.count(fullHistory);
        if (currentTokens <= maxTokenBudget) {
            return fullHistory;
        }

        // Always preserve System Instruction (Index 0)
        Turn systemTurn = fullHistory.get(0);
        List<Turn> candidates = new ArrayList<>(fullHistory.subList(1, fullHistory.size()));
        
        // Evict complete Transaction Units from head of mutable window
        while (currentTokens > maxTokenBudget && !candidates.isEmpty()) {
            Turn evictedTurn = candidates.remove(0); // Atomic turn eviction
            currentTokens -= evictedTurn.cachedTokenCount();
            
            // If the evicted turn triggered tool execution, evict downstream tool responses
            while (!candidates.isEmpty() && candidates.get(0).isSubsequentToolResponse()) {
                Turn toolResponse = candidates.remove(0);
                currentTokens -= toolResponse.cachedTokenCount();
            }
        }

        List<Turn> finalized = new ArrayList<>();
        finalized.add(systemTurn);
        finalized.addAll(candidates);
        return finalized;
    }

    public interface Turn {
        int cachedTokenCount();
        boolean isSubsequentToolResponse();
    }
    
    public interface TokenCounter {
        int count(List<Turn> turns);
    }
}
```

4.  **Handling Massive Tool Output (Context Defense):**
    If a Java method execution returns a massive JSON payload (e.g., 2MB query result):
    *   *Never pass raw DB arrays back to the LLM.*
    *   Enforce a **Local Tool Interceptor**:
        1. Calculate tokens of the result payload.
        2. If tokens exceed threshold (e.g., $> 2,000$ tokens), write the raw payload directly to an ephemeral Redis/S3 key.
        3. Return a summarized representation + key pointer to the LLM:
           ```json
           {
             "status": "TRUNCATED",
             "total_records": 10000,
             "preview": [{"id": 1, "val": "foo"}, {"id": 2, "val": "bar"}],
             "reference_handle": "s3://spill/query_results_91823.json",
             "instruction": "Filter results by specifying narrower parameters to the tool."
           }
           ```

---

### Probing Cheat Sheet: Quick-Fire Architectural Q&A

| Question | Candidate Red Flag | Staff-Level Answer |
| :--- | :--- | :--- |
| **"How do you handle Gemini API key rotation without app restarts?"** | "We restart the deployment or put it in Spring `@RefreshScope`." | "Abstract the key supplier via dynamic configuration (e.g., GCP Secret Manager with memory caching + short TTL). Inject an `Interceptor` that fetches from `AtomicReference<ApiKeyMetadata>` on every outbound HTTP request/gRPC metadata context." |
| **"Why is gRPC better than HTTP/SSE for high-scale Gemini ingress?"** | "Because gRPC is faster / uses binary." | "Binary serialization bypasses Jackson string mapping, reducing allocation velocity. Protobuf frames minimize network payload bytes. HTTP/2 multiplexing natively manages concurrent bidirectional streaming over persistent Netty channels, eliminating connection setup overhead." |
| **"How do you deal with dynamic LLM function calling security?"** | "Just parse the JSON and use Java reflection to invoke the target method." | "Unrestricted reflection leads to Remote Code Execution (RCE). Use an explicit whitelist registry (Command Pattern) mapping function names to strictly typed handler classes. Enforce parameter validation using `Jakarta Validation` (Hibernate Validator) on the deserialized arguments *before* invoking business logic." |
| **"Can Virtual Threads replace Netty entirely for LLM integration?"** | "Yes, Loom makes non-blocking obsolete." | "No. Loom simplifies imperative synchronous programming on blocking I/O, but it still allocates stack resources. For a dedicated edge gateway proxying millions of idle/streaming SSE channels with complex backpressure logic, Netty's reactive event-loop yields a smaller overall footprint and superior low-level socket buffer control." |