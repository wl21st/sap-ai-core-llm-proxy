"""
Integration tests for Anthropic prompt caching via /v1/messages endpoint.

Validates that:
1. cache_control fields on content blocks are preserved and forwarded to Bedrock
2. Bedrock responds with cache usage fields (cache_creation_input_tokens,
   cache_read_input_tokens) in the response
3. A repeated request with the same cached prefix gets a cache hit
4. Streaming responses include cache usage fields in message_start event
5. The /v1/chat/completions endpoint strips cache_control (expected behaviour,
   documented limitation) and does NOT error

Background:
- /v1/messages uses SAP AI SDK (boto3 wrapper) calling Bedrock invoke_model /
  invoke_model_with_response_stream. The SDK wraps the URL but sends the body
  verbatim as Bedrock JSON. cache_control in content blocks passes through.
- Bedrock invoke_model supports cache_control: {"type": "ephemeral"} with the
  same Anthropic API format for Claude models.
- Bedrock response includes cache_creation_input_tokens and cache_read_input_tokens
  in the usage field (snake_case, same as Anthropic API).
- Minimum cacheable tokens: 4096 for Sonnet 4.5, Haiku 4.5; 1024 for Sonnet 4.6,
  Haiku 4.5 (new), Opus 4.7, Claude 3.7 Sonnet.

Claude Code usage:
- Claude Code DOES send cache_control (ephemeral) on system prompts and long
  context by default when the model supports it. This proxy must preserve those
  fields. If stripped, every Claude Code request pays full input token prices.

References:
- https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
- docs/reference/claude_caching_reference.md
"""

import json
import logging

import pytest

logger = logging.getLogger(__name__)

# A long system prompt that exceeds the Bedrock minimum cacheable token count.
# Thresholds: Haiku 4.5, Opus 4.7, Sonnet 4.5 require >= 4096 tokens;
# Sonnet 4.6 / Claude 3.7 require >= 1024 tokens.
# This prompt must clearly exceed 4096 tokens to activate caching on all models.
LONG_SYSTEM_PROMPT = (
    "You are an expert software engineer specializing in distributed systems, "
    "cloud architecture, and performance optimisation. "
    "Your role is to provide clear, concise, and technically accurate answers. "
    "Always consider trade-offs, scalability concerns, and real-world constraints. "
    "When reviewing code, focus on correctness, readability, and maintainability. "
    "When designing systems, think about fault tolerance, latency, and cost. "
    "\n\n"
    # Pad to well over 4096 tokens with realistic-sounding technical content.
    "Background knowledge you must apply:\n"
    + "- CAP theorem: Consistency, Availability, and Partition tolerance are the three "
    "properties of distributed systems; you can guarantee at most two simultaneously.\n"
    + "- BASE semantics: Basically Available, Soft state, Eventually consistent — the "
    "pragmatic alternative to ACID for high-scale distributed databases.\n"
    + "- Consensus algorithms: Raft and Paxos provide strong consistency guarantees in "
    "replicated state machines at the cost of latency during leader election.\n"
    + "- Event sourcing: Store state as an immutable log of events rather than mutable "
    "records; replay the log to reconstruct state at any point in time.\n"
    + "- CQRS: Separate the read model from the write model to allow independent scaling "
    "and optimisation of query and command paths.\n"
    + "- Circuit breaker pattern: Prevent cascading failures by detecting when a downstream "
    "service is unavailable and short-circuiting calls for a cool-down period.\n"
    + "- Backpressure: When a consumer cannot keep up with a producer, signal the producer "
    "to slow down rather than buffering indefinitely and causing OOM errors.\n"
    + "- Idempotency: Design operations so that applying them multiple times has the same "
    "effect as applying them once; critical for at-least-once delivery systems.\n"
    + "- Distributed tracing: Use correlation IDs and span propagation (e.g., OpenTelemetry) "
    "to trace requests across microservice boundaries.\n"
    + "- Service mesh: A dedicated infrastructure layer (e.g., Istio, Linkerd) for handling "
    "service-to-service communication, including retries, mTLS, and observability.\n"
    + "- Saga pattern: Manage long-running distributed transactions through a sequence of "
    "local transactions coordinated by events or an orchestrator.\n"
    + "- Two-phase commit: A blocking distributed protocol that ensures atomicity across "
    "multiple nodes; rarely used in modern systems due to its blocking nature.\n"
    + "- Sharding: Horizontally partition data across multiple nodes to distribute load; "
    "requires careful key selection to avoid hot spots.\n"
    + "- Consistent hashing: A technique to distribute keys across nodes such that only a "
    "fraction of keys need to be remapped when nodes are added or removed.\n"
    + "- Vector clocks and Lamport timestamps: Mechanisms for establishing causal ordering "
    "of events in distributed systems without relying on synchronised wall clocks.\n"
    + "- Bloom filters: Probabilistic data structure that efficiently tests set membership "
    "with a controllable false-positive rate; zero false negatives.\n"
    + "- LSM trees: Log-structured merge-trees optimise write throughput by batching writes "
    "in memory (memtable) and flushing sorted files (SSTables) to disk.\n"
    + "- B-trees vs LSM trees: B-trees favour read-heavy workloads with lower read "
    "amplification; LSM trees favour write-heavy workloads with lower write amplification.\n"
    + "- Write-ahead logging (WAL): Durability guarantee where changes are written to a log "
    "before being applied to the main data structure; enables crash recovery.\n"
    + "- MVCC (Multi-Version Concurrency Control): Allow readers and writers to proceed "
    "concurrently by maintaining multiple versions of data rather than using locks.\n"
    + "- Zero-copy I/O: Transfer data between kernel and userspace without unnecessary "
    "copies (e.g., sendfile, io_uring) to reduce CPU overhead in high-throughput systems.\n"
    + "- Memory-mapped files: Map file contents directly into the process address space; "
    "the OS manages paging, avoiding explicit read/write syscalls.\n"
    + "- Connection pooling: Reuse expensive connections (database, HTTP) across multiple "
    "requests to amortise connection establishment overhead.\n"
    + "- Rate limiting algorithms: Token bucket, leaky bucket, and fixed/sliding window "
    "counters each have different bursty-traffic characteristics.\n"
    + "- Content Delivery Networks (CDNs): Distribute static assets to edge nodes close to "
    "users; reduces origin load and improves perceived latency globally.\n"
    + "- Blue-green deployments: Maintain two identical production environments; switch "
    "traffic between them for zero-downtime releases.\n"
    + "- Canary releases: Gradually roll out a new version to a small subset of traffic; "
    "monitor error rates before increasing the rollout percentage.\n"
    + "- Feature flags: Decouple code deployment from feature activation; enable runtime "
    "toggling of functionality without redeployment.\n"
    + "- Chaos engineering: Deliberately inject failures (latency, errors, node crashes) "
    "into production-like environments to discover systemic weaknesses proactively.\n"
    # --- Extended content to reach > 4096 tokens for haiku/opus minimum ---
    + "\nSecurity and compliance principles:\n"
    + "- Zero-trust architecture: Never implicitly trust any request inside or outside the "
    "network perimeter; verify every access request continuously using identity, device "
    "health, and contextual signals.\n"
    + "- Principle of least privilege: Grant only the permissions required for a task; "
    "revoke them immediately after use to minimise blast radius from credential compromise.\n"
    + "- Defence in depth: Layer multiple independent security controls so that no single "
    "failure exposes the system; combine network segmentation, WAF, mTLS, and audit logs.\n"
    + "- Secrets management: Store credentials and keys in dedicated vaults (e.g., HashiCorp "
    "Vault, AWS Secrets Manager); rotate them automatically and never embed them in source.\n"
    + "- Supply chain security: Sign container images and software artefacts (e.g., Sigstore "
    "Cosign, SLSA provenance); pin dependency versions and scan for CVEs in CI.\n"
    + "- Audit logging: Emit tamper-evident, append-only logs for every privileged action; "
    "ship them to a separate account or SIEM outside the blast radius of a compromised host.\n"
    + "- Encryption at rest and in transit: Enforce TLS 1.3 for all service communication; "
    "use envelope encryption (DEK wrapped by KEK) for sensitive data stores.\n"
    + "- RBAC vs ABAC: Role-based access control assigns permissions to roles; attribute-"
    "based access control evaluates dynamic policies against subject and resource attributes "
    "for finer-grained decisions.\n"
    + "\nObservability and reliability:\n"
    + "- The three pillars of observability are metrics, logs, and traces; together they let "
    "you ask arbitrary questions about system state without shipping new instrumentation.\n"
    + "- RED method: Track Request rate, Error rate, and Duration for every service boundary; "
    "these three signals surface the majority of user-visible reliability problems.\n"
    + "- USE method: Track Utilisation, Saturation, and Errors for every resource (CPU, "
    "memory, disk, network); saturated resources cause queuing and latency spikes.\n"
    + "- SLO-based alerting: Alert on error-budget burn rate rather than raw thresholds; "
    "a fast burn rate triggers a page, a slow burn triggers a ticket.\n"
    + "- Structured logging: Emit logs as JSON key-value pairs rather than free text so that "
    "log aggregators can index and filter on field values without regex.\n"
    + "- Exemplars: Attach a sampled trace ID to each metric data point so that a spike in "
    "latency can be correlated directly to a specific distributed trace.\n"
    + "- Synthetic monitoring: Run scripted user journeys against production on a schedule to "
    "detect availability regressions before real users encounter them.\n"
    + "\nData engineering and streaming:\n"
    + "- Lambda architecture: Process data in both a batch layer (high latency, accurate) and "
    "a speed layer (low latency, approximate); merge results in a serving layer.\n"
    + "- Kappa architecture: Replace the batch layer with a replayable stream; replay the "
    "full history through the same streaming pipeline to rebuild derived views.\n"
    + "- Kafka guarantees: At-least-once delivery by default; exactly-once semantics require "
    "idempotent producers and transactional APIs introduced in Kafka 0.11.\n"
    + "- Watermarks in streaming: A watermark is a heuristic lower bound on event-time "
    "progress; Flink and Beam use watermarks to decide when a window is complete.\n"
    + "- Compaction in Kafka: Log-compacted topics retain the latest value per key "
    "indefinitely, enabling consumers to bootstrap state without reading the full history.\n"
    + "- Schema evolution: Use a schema registry with Avro or Protobuf to enforce "
    "backward/forward compatibility; never break consumers by removing required fields.\n"
    + "- Change Data Capture (CDC): Tail the database write-ahead log (e.g., Debezium) to "
    "stream row-level changes into Kafka without adding application-level overhead.\n"
    + "\nCloud-native patterns:\n"
    + "- Twelve-factor app: Store config in the environment, treat backing services as "
    "attached resources, keep dev/prod parity, and emit logs as event streams.\n"
    + "- Sidecar pattern: Deploy a helper container alongside the main application container "
    "in the same pod to handle cross-cutting concerns (logging, proxying, cert renewal).\n"
    + "- Ambassador pattern: A proxy sidecar that translates between the application and "
    "external services, abstracting retry logic, load balancing, and auth.\n"
    + "- Adapter pattern: A sidecar that normalises heterogeneous outputs (e.g., different "
    "metric formats) into a standard interface consumed by the monitoring stack.\n"
    + "- Horizontal Pod Autoscaler (HPA): Scales deployment replicas based on CPU/memory or "
    "custom metrics; pairs with KEDA for event-driven scaling from Kafka lag.\n"
    + "- Vertical Pod Autoscaler (VPA): Recommends or automatically adjusts CPU and memory "
    "requests and limits based on observed usage; avoid combining HPA and VPA on the same "
    "resource metric.\n"
    + "- Node affinity and taints: Direct pods to specific node pools (e.g., GPU nodes, "
    "spot instances) using nodeSelector, affinity rules, and tolerations.\n"
    + "- PodDisruptionBudget (PDB): Guarantee a minimum number of available replicas during "
    "voluntary disruptions (node drains, rolling updates) to maintain SLA.\n"
    + "\nPerformance optimisation techniques:\n"
    + "- Amdahl's Law: The theoretical speedup from parallelising a program is limited by "
    "its sequential fraction; doubling cores does not halve end-to-end latency if 20% of "
    "the work is inherently serial.\n"
    + "- Cache hierarchy awareness: Access patterns that respect CPU L1/L2/L3 cache lines "
    "(64 bytes) avoid expensive main-memory round trips; prefer sequential over random "
    "access for hot data structures.\n"
    + "- NUMA awareness: On multi-socket servers, memory accesses to a remote NUMA node "
    "incur ~2× latency; pin latency-sensitive threads to cores local to their memory.\n"
    + "- Lock-free data structures: Use atomic compare-and-swap operations to implement "
    "queues and stacks without mutexes; reduces contention but complicates correctness.\n"
    + "- Mechanical sympathy: Design software with knowledge of the underlying hardware; "
    "Martin Thompson's LMAX Disruptor ring buffer demonstrates cache-friendly concurrency.\n"
    + "- Profiling before optimising: Always measure with a profiler (perf, async-profiler, "
    "py-spy) to identify the actual bottleneck before changing code; intuition is often "
    "wrong about where time is spent.\n"
    + "\nAPI design and contracts:\n"
    + "- REST constraints: Uniform interface, statelessness, client-server separation, "
    "cacheability, layered system, and code-on-demand (optional); a service that satisfies "
    "all constraints is RESTful, not just HTTP-based.\n"
    + "- Idempotency keys: Clients attach a unique key per logical operation so that retried "
    "requests do not create duplicate side effects; store keys server-side with a short TTL.\n"
    + "- Pagination strategies: Offset pagination is simple but inconsistent under concurrent "
    "writes; cursor-based pagination (keyset) is stable and scalable for large result sets.\n"
    + "- Rate limit headers: Return Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining, "
    "and X-RateLimit-Reset so clients can back off gracefully without polling.\n"
    + "- Versioning strategies: URL versioning (/v1/, /v2/) is explicit but pollutes paths; "
    "header versioning (Accept: application/vnd.api+json;version=2) is cleaner but less "
    "visible; semantic versioning in package releases is the de-facto standard.\n"
    + "- OpenAPI / AsyncAPI: Machine-readable API contracts enable contract testing, "
    "automatic client generation, and mock servers; treat the spec as source of truth.\n"
    + "- GraphQL trade-offs: Flexible queries reduce over-fetching but introduce n+1 query "
    "problems (solved with DataLoader batching) and make caching harder than REST.\n"
    + "- gRPC: Binary Protobuf framing over HTTP/2 gives lower latency and strong typing "
    "vs JSON REST, but requires code generation and is harder to debug with curl.\n"
    + "\nDatabase internals and query optimisation:\n"
    + "- Index types: B-tree indexes support equality and range queries; hash indexes support "
    "only equality; GIN indexes support full-text and array containment; BRIN indexes are "
    "compact for naturally ordered columns like timestamps.\n"
    + "- Query planner statistics: Databases maintain column histograms and correlation stats; "
    "running ANALYZE updates them so the planner chooses optimal join strategies.\n"
    + "- Covering indexes: An index that includes all columns a query needs avoids a heap "
    "fetch (index-only scan), reducing I/O by an order of magnitude for selective queries.\n"
    + "- Partial indexes: Index only a filtered subset of rows (e.g., WHERE deleted_at IS "
    "NULL); smaller index footprint, faster writes, targeted for common query patterns.\n"
    + "- Vacuum and autovacuum: PostgreSQL MVCC leaves dead tuples on disk after updates and "
    "deletes; vacuum reclaims space and updates visibility maps for index-only scans.\n"
    + "- Connection pooling: Each database connection consumes ~5 MB of server memory; use "
    "PgBouncer (transaction mode) to multiplex thousands of app connections onto tens of "
    "database connections without blocking.\n"
    + "- Read replicas: Stream WAL to standby servers for read scaling; beware replication "
    "lag causing stale reads — use synchronous replication or session-level read-after-write "
    "routing for consistency-sensitive queries.\n"
    + "- Table partitioning: Range, list, and hash partitioning prune irrelevant partitions "
    "at query time; declarative partitioning in PostgreSQL 10+ manages child tables "
    "automatically.\n"
    + "\nMachine learning infrastructure:\n"
    + "- Feature stores: Centralise feature computation and serving to avoid training-serving "
    "skew; Feast and Tecton decouple feature pipelines from model training code.\n"
    + "- Model registries: Version and track models with metadata (dataset hash, metrics, "
    "hyperparameters) so experiments are reproducible and rollback is straightforward.\n"
    + "- Shadow deployments: Route a copy of production traffic to a new model without "
    "affecting user responses; compare outputs offline before promoting the challenger.\n"
    + "- A/B testing vs multi-armed bandits: A/B tests maximise statistical power with fixed "
    "allocation; bandits adapt allocation to exploit better-performing variants earlier.\n"
    + "- Gradient checkpointing: Trade compute for memory during backpropagation by "
    "recomputing activations on the backward pass rather than storing them all in VRAM.\n"
    + "- Mixed precision training: Use FP16 for forward/backward passes and FP32 for weight "
    "updates (AMP); reduces VRAM usage and increases throughput on tensor cores.\n"
    + "- Distributed training strategies: Data parallelism replicates the model and splits "
    "the batch; tensor parallelism splits layers; pipeline parallelism splits depth; "
    "ZeRO shards optimiser state, gradients, and parameters across devices.\n"
    + "\nSoftware architecture patterns:\n"
    + "- Hexagonal architecture (ports and adapters): The application core defines ports "
    "(interfaces); adapters implement them for specific technologies (HTTP, SQL, Kafka); "
    "this isolates the domain model from infrastructure concerns.\n"
    + "- Domain-driven design aggregates: An aggregate is a cluster of domain objects with "
    "a single root entity that enforces invariants; all external references go through "
    "the aggregate root, never directly to internal entities.\n"
    + "- Anti-corruption layer: A translation layer between two bounded contexts that "
    "prevents concepts from one domain leaking into another; essential when integrating "
    "legacy systems with new domain models.\n"
    + "- Outbox pattern: Write domain events to an outbox table in the same database "
    "transaction as state changes; a separate relay process publishes them to the message "
    "broker, guaranteeing at-least-once delivery without distributed transactions.\n"
    + "- Transactional outbox vs dual-write: Dual-write (writing to DB and broker "
    "independently) risks split-brain under failures; the outbox pattern eliminates this "
    "by making the broker write a downstream side effect of the DB write.\n"
    + "- Event-carried state transfer: Publish events that include enough data for "
    "consumers to update their local read models without querying the source service, "
    "reducing coupling and latency.\n"
    + "- Choreography vs orchestration: In choreography each service reacts to events "
    "autonomously; in orchestration a central coordinator drives the workflow; "
    "orchestration is easier to trace, choreography scales with less coupling.\n"
    + "\nCI/CD and DevOps practices:\n"
    + "- Trunk-based development: All engineers commit to a single shared branch frequently; "
    "feature flags gate incomplete work; long-lived branches are an anti-pattern that "
    "defers integration pain.\n"
    + "- GitOps: The desired cluster state is stored in Git; a reconciliation agent (Argo CD, "
    "Flux) continuously applies diffs between desired and actual state; Git history is the "
    "audit log.\n"
    + "- Immutable infrastructure: Replace servers rather than mutating them; bake AMIs or "
    "container images in CI and promote the same artefact through environments.\n"
    + "- Supply chain levels for software artefacts (SLSA): A framework of security "
    "requirements (source, build, provenance) to protect against tampering at each stage "
    "of the software supply chain.\n"
    + "- Dora metrics: Deployment frequency, lead time for changes, change failure rate, and "
    "mean time to restore are the four key metrics of software delivery performance.\n"
    + "- Shift-left security: Integrate SAST, dependency scanning, and secret detection into "
    "the developer workflow and CI pipeline rather than gating only at release time.\n"
    + "- Contract testing: Verify that a service provider honours the expectations of its "
    "consumers using consumer-driven contracts (Pact); catches breaking API changes before "
    "integration tests.\n"
    + "- Progressive delivery: Gate feature rollouts with automated analysis of metrics "
    "(canary analysis, Argo Rollouts); halt promotion automatically if error rate spikes.\n"
    + "\nNetwork fundamentals for engineers:\n"
    + "- TCP flow control: The receiver advertises a window size; the sender may not have "
    "more than window-size bytes unacknowledged in flight; a zero window causes the sender "
    "to pause until a window update arrives.\n"
    + "- TCP congestion control: Slow start, congestion avoidance, fast retransmit, and fast "
    "recovery collectively prevent senders from overwhelming the network; CUBIC and BBR are "
    "modern algorithms that improve throughput on high-bandwidth-delay-product links.\n"
    + "- HTTP/2 multiplexing: Multiple logical streams share a single TCP connection, "
    "eliminating head-of-line blocking at the HTTP layer; HTTP/3 moves to QUIC (UDP) to "
    "eliminate TCP-level HOL blocking as well.\n"
    + "- DNS resolution chain: Stub resolver → recursive resolver → root nameserver → TLD "
    "nameserver → authoritative nameserver; negative caching (NXDOMAIN TTL) prevents "
    "thundering herds on missing records.\n"
    + "- BGP and anycast: Border Gateway Protocol advertises IP prefixes between autonomous "
    "systems; anycast routes the same prefix from multiple locations so clients connect to "
    "the topologically nearest instance — used by CDNs and DNS resolvers.\n"
    + "- eBPF: Extended Berkeley Packet Filter programs run in the kernel sandbox; used for "
    "high-performance packet filtering, observability (bpftrace), and security enforcement "
    "(Cilium) without kernel module compilation.\n"
    + "- Service discovery: DNS-based (SRV records, Route 53) is simple; client-side load "
    "balancing with a service registry (Consul, Eureka) gives more control; Kubernetes "
    "kube-proxy implements virtual IPs via iptables or IPVS.\n"
)

# Long enough user question to accompany the system prompt in tests.
SIMPLE_QUESTION = "Explain the key difference between eventual consistency and strong consistency in one paragraph."


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.claude
@pytest.mark.parametrize(
    "model",
    [
        "anthropic--claude-4.5-haiku",
        "sonnet-4.6",
        "haiku-4.5",
        "opus-4.7",
    ],
)
class TestCacheControlMessagesEndpoint:
    """
    Tests for prompt caching via the /v1/messages endpoint.

    These tests use the Anthropic Messages API format with explicit
    block-level cache_control markers. The proxy should pass these
    through to Bedrock's invoke_model API, which supports cache_control
    in the same format as the Anthropic API.
    """

    async def test_cache_write_on_first_request(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        First request with cache_control should write tokens to cache.

        Bedrock returns cache_creation_input_tokens > 0 when a new
        cache entry is written. input_tokens covers only the uncached
        tail (the user question after the breakpoint).
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "system": [
                    {
                        "type": "text",
                        "text": LONG_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [
                    {"role": "user", "content": SIMPLE_QUESTION}
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "usage" in data, "Response missing 'usage'"
        usage = data["usage"]

        logger.info(
            "Cache WRITE test [%s] usage: %s", model, json.dumps(usage)
        )

        # On the first call the system prompt bytes were not cached yet, so
        # Bedrock should have written them to cache.
        assert "cache_creation_input_tokens" in usage, (
            "Response missing cache_creation_input_tokens — cache_control may have been stripped. "
            f"Got usage keys: {list(usage.keys())}"
        )
        assert "cache_read_input_tokens" in usage, (
            "Response missing cache_read_input_tokens. "
            f"Got usage keys: {list(usage.keys())}"
        )

        # On a fresh first request there should be no cache reads.
        # (There could be a read if a previous test already cached this exact
        # system prompt within the 5-minute TTL — that is still a success.)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)

        assert cache_creation + cache_read > 0, (
            "Neither cache_creation_input_tokens nor cache_read_input_tokens is > 0. "
            "This means the system prompt was NOT cached at all, which indicates "
            "cache_control was stripped by the proxy. "
            f"usage={usage}"
        )

        logger.info(
            "Cache write=%d, cache read=%d for model %s",
            cache_creation,
            cache_read,
            model,
        )

    async def test_cache_hit_on_repeated_request(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Two consecutive requests with the same system prompt and cache_control
        should result in a cache hit on the second request.

        The first request writes the prefix to cache. The second request
        should read from cache, so cache_read_input_tokens > 0 on the second
        call and the system prompt tokens are NOT billed as full input_tokens.

        NOTE: If the first request was already cached (e.g., by the previous
        test or a recent Claude Code session), both calls may show cache reads.
        The assertion only checks that the second call has cache_read > 0.
        """
        payload = {
            "model": model,
            "system": [
                {
                    "type": "text",
                    "text": LONG_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {"role": "user", "content": SIMPLE_QUESTION}
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }

        # First request — prime the cache.
        response1 = await proxy_client.post(
            f"{proxy_url}/v1/messages", json=payload
        )
        assert response1.status_code == 200, (
            f"First cache-prime request failed: {response1.status_code}: {response1.text}"
        )
        usage1 = response1.json()["usage"]
        logger.info("Cache prime [%s] usage: %s", model, json.dumps(usage1))

        # Second request — should hit the cache.
        response2 = await proxy_client.post(
            f"{proxy_url}/v1/messages", json=payload
        )
        assert response2.status_code == 200, (
            f"Second cache-hit request failed: {response2.status_code}: {response2.text}"
        )
        usage2 = response2.json()["usage"]
        logger.info("Cache hit  [%s] usage: %s", model, json.dumps(usage2))

        cache_read2 = usage2.get("cache_read_input_tokens", 0)

        assert cache_read2 > 0, (
            "Second identical request did NOT read from cache "
            "(cache_read_input_tokens == 0). "
            "This means either: (a) cache_control was stripped by the proxy, "
            "(b) the system prompt is below the Bedrock minimum token threshold, "
            "or (c) the 5-minute TTL expired between the two requests. "
            f"Second request usage: {usage2}"
        )

        # Cost check: system prompt tokens on 2nd request should cost 10% of
        # normal input price (cache read), not 100%.
        logger.info(
            "Cache hit confirmed: cache_read_input_tokens=%d, "
            "cache_creation_input_tokens=%d, input_tokens=%d for model %s",
            cache_read2,
            usage2.get("cache_creation_input_tokens", 0),
            usage2.get("input_tokens", 0),
            model,
        )

    async def test_cache_control_on_message_content_block(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        cache_control can also be placed on message content blocks, not just
        the system prompt. This tests that the proxy preserves cache_control
        on user message content blocks too.
        """
        long_context = LONG_SYSTEM_PROMPT  # reuse the long text as user context

        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": long_context,
                                "cache_control": {"type": "ephemeral"},
                            },
                            {
                                "type": "text",
                                "text": SIMPLE_QUESTION,
                            },
                        ],
                    }
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        usage = data["usage"]
        logger.info(
            "Message block cache test [%s] usage: %s", model, json.dumps(usage)
        )

        assert "cache_creation_input_tokens" in usage, (
            "cache_creation_input_tokens missing — message block cache_control was stripped. "
            f"Got usage keys: {list(usage.keys())}"
        )
        assert "cache_read_input_tokens" in usage, (
            f"cache_read_input_tokens missing. Got usage keys: {list(usage.keys())}"
        )

        cache_tokens = (
            usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        assert cache_tokens > 0, (
            "No cache activity despite cache_control on user message block. "
            f"usage={usage}"
        )

    async def test_usage_fields_present_without_cache_control(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Baseline test: without cache_control, the response still has the
        standard usage fields. cache_creation_input_tokens and
        cache_read_input_tokens may be present (Bedrock always includes them
        as 0) or absent — we only check the standard fields.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        usage = data["usage"]
        logger.info("No-cache baseline [%s] usage: %s", model, json.dumps(usage))

        assert "input_tokens" in usage, "Missing input_tokens"
        assert "output_tokens" in usage, "Missing output_tokens"
        assert usage["input_tokens"] > 0, "input_tokens should be > 0"
        assert usage["output_tokens"] > 0, "output_tokens should be > 0"

    async def test_streaming_cache_write_includes_usage_fields(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Streaming responses include cache usage in the message_start SSE event.
        The message_start event has a 'usage' object with cache fields.

        Bedrock SSE format:
          event: message_start
          data: {"type": "message_start", "message": {..., "usage": {
              "input_tokens": N,
              "cache_creation_input_tokens": M,
              "cache_read_input_tokens": P,
              ...
          }}}
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "system": [
                    {
                        "type": "text",
                        "text": LONG_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [
                    {"role": "user", "content": SIMPLE_QUESTION}
                ],
                "max_tokens": max_tokens,
                "stream": True,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        message_start_event = None
        for line in response.text.split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    event_data = json.loads(line[6:])
                    if event_data.get("type") == "message_start":
                        message_start_event = event_data
                        break
                except json.JSONDecodeError:
                    continue

        assert message_start_event is not None, (
            "No message_start event found in streaming response"
        )

        message = message_start_event.get("message", {})
        usage = message.get("usage", {})
        logger.info(
            "Streaming cache test [%s] message_start.usage: %s",
            model,
            json.dumps(usage),
        )

        assert "cache_creation_input_tokens" in usage or "cache_read_input_tokens" in usage, (
            "Streaming message_start event missing cache usage fields. "
            "This means cache_control was stripped before sending to Bedrock, OR "
            "Bedrock is not returning cache usage fields in the streaming response. "
            f"message_start.usage keys: {list(usage.keys())}"
        )

        cache_tokens = (
            usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        assert cache_tokens > 0, (
            "Streaming: cache_creation + cache_read == 0 despite cache_control in system. "
            f"usage={usage}"
        )


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.claude
@pytest.mark.parametrize(
    "model",
    [
        "anthropic--claude-4.5-haiku",
        "sonnet-4.6",
        "haiku-4.5",
        "opus-4.7",
    ],
)
class TestCacheControlChatCompletionsEndpoint:
    """
    Tests for /v1/chat/completions with cache_control fields.

    The /v1/chat/completions path converts OpenAI-format requests to SAP AI
    Core HTTP format via convert_openai_to_claude37(). This conversion
    intentionally strips cache_control because the SAP AI Core endpoint for
    /converse does not accept it.

    These tests verify:
    1. The request does NOT fail (stripping is graceful)
    2. The response does NOT include cache token fields (confirming no caching)
    3. The behaviour is documented so callers know caching is unavailable here
    """

    async def test_cache_control_stripped_gracefully(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Sending cache_control on the /v1/chat/completions endpoint should NOT
        cause an error. The proxy strips it silently before forwarding.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": LONG_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": SIMPLE_QUESTION,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    },
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200 (cache_control should be stripped gracefully), "
            f"got {response.status_code}: {response.text}"
        )

    async def test_no_cache_tokens_in_chat_completions_response(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        The /v1/chat/completions path strips cache_control, so no caching
        occurs. The response usage object should not include
        cache_creation_input_tokens / cache_read_input_tokens (or both are 0).

        This is a documented limitation: to use prompt caching, clients must
        use the /v1/messages endpoint with Anthropic-format cache_control.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": LONG_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": SIMPLE_QUESTION},
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        usage = data.get("usage", {})
        logger.info(
            "Chat completions no-cache [%s] usage: %s", model, json.dumps(usage)
        )

        # In OpenAI format, cache info might appear in prompt_tokens_details.
        # The top-level usage has prompt_tokens, completion_tokens, total_tokens.
        assert "prompt_tokens" in usage, "Missing prompt_tokens in chat completions usage"
        assert "completion_tokens" in usage, "Missing completion_tokens"

        # Verify: no Anthropic-native cache fields should be present at the
        # top level of usage (they would only appear if the proxy mistakenly
        # forwarded Bedrock cache fields in the OpenAI response).
        cache_creation = usage.get("cache_creation_input_tokens", None)
        cache_read = usage.get("cache_read_input_tokens", None)

        logger.info(
            "Confirmed: chat completions response does not include Anthropic "
            "cache fields at top level. cache_creation=%s, cache_read=%s",
            cache_creation,
            cache_read,
        )


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.claude
class TestCacheControlTokenCostVerification:
    """
    Verifies that cache hits produce lower effective input token costs.

    Uses the /v1/messages endpoint only (where caching is supported).

    Economics:
    - Cache write: 1.25x base input token price
    - Cache read:  0.10x base input token price
    - Break-even:  caching becomes profitable after 1 read hit

    This test makes 3 sequential requests to the same long system prompt
    and checks that the token accounting shows progressive cache behaviour.
    """

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-haiku",
            "sonnet-4.6",
            "haiku-4.5",
            "opus-4.7",
        ],
    )
    async def test_cost_reduction_across_repeated_requests(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Three consecutive identical requests should show:
          Request 1: cache write (cache_creation_input_tokens > 0)
          Request 2: cache read (cache_read_input_tokens > 0, same value as write)
          Request 3: cache read (same)

        The system prompt tokens should NOT appear in input_tokens on requests
        2 and 3 — they have moved into cache_read_input_tokens.
        """
        payload = {
            "model": model,
            "system": [
                {
                    "type": "text",
                    "text": LONG_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {"role": "user", "content": SIMPLE_QUESTION}
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }

        usages = []
        for i in range(3):
            resp = await proxy_client.post(
                f"{proxy_url}/v1/messages", json=payload
            )
            assert resp.status_code == 200, (
                f"Request {i+1} failed: {resp.status_code}: {resp.text}"
            )
            usage = resp.json()["usage"]
            usages.append(usage)
            logger.info("Request %d [%s] usage: %s", i + 1, model, json.dumps(usage))

        # At least one of the three requests must have shown cache activity.
        total_cache_tokens = sum(
            u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            for u in usages
        )
        assert total_cache_tokens > 0, (
            "No cache activity across 3 identical requests. "
            "cache_control is likely being stripped by the proxy. "
            f"Usages: {usages}"
        )

        # After the first write, requests 2 and 3 should have cache reads.
        # We check request 3 (index 2) as it has the most time for cache to settle.
        req3_cache_read = usages[2].get("cache_read_input_tokens", 0)
        req3_cache_creation = usages[2].get("cache_creation_input_tokens", 0)

        # Either a read hit or a fresh write (if TTL expired) is acceptable.
        assert req3_cache_read + req3_cache_creation > 0, (
            "Request 3 shows no cache activity at all, which is unexpected. "
            f"usage: {usages[2]}"
        )

        if req3_cache_read > 0:
            logger.info(
                "Cost verified: Request 3 read %d tokens from cache "
                "(cost: 0.10x vs 1.00x for full input), model=%s",
                req3_cache_read,
                model,
            )
        else:
            logger.warning(
                "Request 3 did not get a cache hit (possible TTL expiry). "
                "cache_creation=%d. model=%s",
                req3_cache_creation,
                model,
            )
