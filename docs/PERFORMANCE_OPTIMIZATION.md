# Performance Optimization Guide

This document describes performance optimizations implemented in the Ultimate MCP Platform and recommendations for production deployments.

## Database Performance Optimizations

### Neo4j Indexes

The following indexes are automatically created on startup to optimize common query patterns:

#### Audit and Security Queries
```cypher
CREATE INDEX audit_event_timestamp FOR (n:AuditEvent) ON (n.timestamp)
CREATE INDEX audit_event_user FOR (n:AuditEvent) ON (n.user_id)
CREATE INDEX audit_event_type FOR (n:AuditEvent) ON (n.event_type)
```

**Use Case**: Fast retrieval of audit logs by user, time range, or event type

#### Execution Results
```cypher
CREATE INDEX execution_timestamp FOR (n:ExecutionResult) ON (n.timestamp)
CREATE INDEX execution_code_hash FOR (n:ExecutionResult) ON (n.code_hash)
CREATE INDEX execution_language FOR (n:ExecutionResult) ON (n.language)
CREATE INDEX execution_user_time FOR (n:ExecutionResult) ON (n.user_id, n.timestamp)
```

**Use Case**: Query execution history, detect duplicate executions via code_hash, filter by language

#### Lint Results
```cypher
CREATE INDEX lint_result_hash FOR (n:LintResult) ON (n.code_hash)
CREATE INDEX lint_result_timestamp FOR (n:LintResult) ON (n.timestamp)
```

**Use Case**: Lookup lint results for previously analyzed code, time-based queries

#### Test Results
```cypher
CREATE INDEX test_result_timestamp FOR (n:TestResult) ON (n.timestamp)
```

**Use Case**: Time-series analysis of test executions

### Connection Pooling

The Neo4j client now supports configurable connection pooling:

```python
from mcp_server.database.neo4j_client import Neo4jClient

client = Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    database="neo4j",
    max_connection_pool_size=100,  # Default: 100 connections
    connection_acquisition_timeout=60.0,  # Default: 60 seconds
)
```

**Recommendations**:
- **Low traffic** (< 10 RPS): 20-50 connections
- **Medium traffic** (10-100 RPS): 50-100 connections  
- **High traffic** (> 100 RPS): 100-200 connections

### Retry Logic

The `EnhancedNeo4jClient` provides automatic retry with exponential backoff for transient errors:

```python
from mcp_server.database.neo4j_client_enhanced import EnhancedNeo4jClient

client = EnhancedNeo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    database="neo4j",
    max_retries=3,  # Default: 3 retries
    initial_backoff_seconds=0.2,  # Default: 200ms
)

# Automatic retry on transient failures
await client.execute_write_with_retry(query, parameters)
```

## Application Performance

### Caching

The execution tool includes result caching to avoid re-executing identical code:

```python
# Cache configuration in config.py
cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
cache_size: int = Field(default=1000, env="CACHE_SIZE")
cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL")
```

**Benefits**:
- Reduces execution time for repeated code snippets
- Lowers resource utilization
- Improves response times

### Rate Limiting

SlowAPI rate limiting is configured per-endpoint:

```python
# Default: 10 requests per second
RATE_LIMIT = f"{settings.rate_limit_rps}/second"

@app.post("/execute_code")
@limiter.limit("10/minute")  # Custom limit
async def execute_code(...):
    ...
```

**Recommendations**:
- Adjust `RATE_LIMIT_RPS` based on backend capacity
- Use Redis backend for distributed rate limiting
- Monitor rate limit hits via metrics

### Resource Limits

Execution sandbox enforces resource limits to prevent abuse:

```python
# Configurable via environment variables
MAX_EXECUTION_TIME=30.0  # seconds
MAX_MEMORY_MB=128  # megabytes
MAX_FILE_SIZE_MB=10  # megabytes
MAX_PROCESSES=1  # concurrent processes
```

## Monitoring and Profiling

### Metrics Collection

Enable metrics to track performance:

```python
METRICS_ENABLED=true
METRICS_PORT=9090
```

**Available Metrics**:
- Request count and latency
- Execution success/failure rates
- Cache hit rates
- Database query performance
- Memory and CPU usage

### Slow Query Detection

Configure slow query threshold:

```python
SLOW_QUERY_THRESHOLD=1.0  # seconds
```

Queries exceeding this threshold are logged for investigation.

### Profiling

Enable profiling for performance analysis:

```python
ENABLE_PROFILING=true
```

**Note**: Only enable in development/staging environments.

## Query Optimization Best Practices

### 1. Use Parameterized Queries

```python
# Good: Uses parameters
query = "MATCH (n:Node {id: $id}) RETURN n"
await client.execute_read(query, {"id": node_id})

# Bad: String concatenation (also unsafe)
query = f"MATCH (n:Node {{id: '{node_id}'}}) RETURN n"
```

### 2. Limit Result Sets

```python
# Always use LIMIT for potentially large result sets
query = "MATCH (n:AuditEvent) WHERE n.timestamp > $since RETURN n LIMIT 1000"
```

### 3. Use Indexes

```python
# Ensure your WHERE clauses use indexed properties
query = "MATCH (n:ExecutionResult) WHERE n.code_hash = $hash RETURN n"
# code_hash is indexed, so this query is fast
```

### 4. Batch Operations

```python
# Good: Single query with multiple operations
query = """
UNWIND $nodes AS node
CREATE (n:Node)
SET n = node
"""
await client.execute_write(query, {"nodes": node_list})

# Bad: Multiple individual queries
for node in node_list:
    await client.execute_write("CREATE (n:Node) SET n = $node", {"node": node})
```

## Production Deployment Recommendations

### 1. Connection Pooling
- Set `max_connection_pool_size=100` for high-traffic deployments
- Monitor pool saturation via Neo4j metrics

### 2. Caching
- Enable Redis for distributed caching: `REDIS_ENABLED=true`
- Set appropriate TTL based on data volatility

### 3. Rate Limiting
- Use Redis backend for distributed rate limiting
- Adjust limits based on capacity testing

### 4. Resource Limits
- Set conservative execution limits in production
- Monitor execution timeouts and adjust as needed

### 5. Database Tuning
- Ensure all indexes are created (automatic on startup)
- Monitor index usage with `PROFILE` queries
- Consider query result caching for read-heavy workloads

### 6. Monitoring
- Enable metrics collection: `METRICS_ENABLED=true`
- Set up alerting for slow queries and high error rates
- Monitor resource utilization (CPU, memory, connections)

## Performance Testing

### Benchmark Script

```bash
# Install dependencies
pip install locust

# Run load test
locust -f tests/performance/locustfile.py --host http://localhost:8000
```

### Expected Performance (Baseline)

**Hardware**: 4 CPU, 8GB RAM, SSD
**Database**: Neo4j 5.23 (local)

- **Health check**: < 10ms (p50), < 20ms (p99)
- **Lint code**: < 100ms (p50), < 500ms (p99)
- **Execute code**: < 200ms (p50), < 1000ms (p99)
- **Query graph**: < 50ms (p50), < 200ms (p99)
- **Cache hit**: < 5ms (p50), < 10ms (p99)

## Troubleshooting Performance Issues

### Symptom: Slow Database Queries

**Diagnosis**:
```cypher
PROFILE MATCH (n:ExecutionResult) WHERE n.user_id = $user RETURN n
```

**Solution**:
- Check if indexes are created: `SHOW INDEXES`
- Verify query uses indexed properties
- Consider composite index for multi-property queries

### Symptom: High Memory Usage

**Diagnosis**:
- Check execution result cache size
- Monitor Neo4j memory configuration
- Check for memory leaks in long-running processes

**Solution**:
- Reduce `CACHE_SIZE`
- Tune Neo4j heap settings
- Add memory limits to Docker containers

### Symptom: Connection Pool Exhaustion

**Diagnosis**:
- Monitor active connections in Neo4j
- Check for connection leaks (sessions not closed)

**Solution**:
- Increase `max_connection_pool_size`
- Ensure all sessions use context managers
- Check for long-running transactions

### Symptom: Rate Limit Throttling

**Diagnosis**:
- Check rate limit hit metrics
- Monitor request patterns

**Solution**:
- Increase `RATE_LIMIT_RPS` if legitimate traffic
- Implement client-side backoff and retry
- Consider burst allowance configuration

## Next Steps

1. **Load Testing**: Run Locust tests to establish baseline performance
2. **Monitoring**: Set up Prometheus + Grafana for metrics visualization
3. **Profiling**: Use py-spy or cProfile to identify bottlenecks
4. **Optimization**: Based on profiling results, optimize hot paths
5. **Scaling**: Consider horizontal scaling for high-traffic scenarios
