# Performance Optimizations in Planfile

This document outlines the performance optimizations implemented to improve planfile's startup time and runtime efficiency.

## Optimizations Implemented

### 1. Lazy Loading in `__init__.py`

**Problem**: Heavy modules (runner, executor_standalone) were imported upfront, causing slow startup.

**Solution**: Implemented lazy loading using `__getattr__` and `TYPE_CHECKING`:
- Executors are only imported when actually accessed
- Type hints are preserved for IDE support
- Reduces initial import time significantly

### 2. Subprocess Caching in `runner.py`

**Problem**: `analyze_project_metrics()` ran pytest coverage on every call, which is expensive.

**Solution**: Added intelligent caching with:
- 5-minute cache for coverage results in `~/.planfile_cache/`
- Project hash-based cache invalidation
- 30-second timeout for pytest execution
- Fallback to `rg` (ripgrep) for faster file counting when available

### 3. Thread-Safe File Caching in `store.py`

**Problem**: Frequent YAML file reads/writes without caching caused I/O bottlenecks.

**Solution**: Implemented:
- In-memory cache with modification time-based invalidation
- Thread-safe operations using locks
- Cache size limit (100 files) to prevent memory bloat
- FIFO eviction when cache is full

### 4. Timeout Protection in Examples

**Problem**: Example scripts could hang indefinitely, causing "długie przestoje" (long delays).

**Solution**: Added 60-second timeout to example execution with proper cleanup.

## Cache Management

### Clearing Caches

If you encounter issues with stale data, clear caches:

```bash
# Clear subprocess cache
rm -rf ~/.planfile_cache/

# File cache is in-memory and clears on restart
```

### Cache Locations

- Subprocess cache: `~/.planfile_cache/coverage_*.json`
- File cache: In-memory only (cleared on process exit)

## Performance Tips

1. **Use ripgrep**: Install `rg` for faster file counting in project metrics
2. **Avoid frequent verification**: The `verify_strategy_post_execution` function is now cached
3. **Batch operations**: Use `list_tickets(sprint="all")` efficiently with caching

## Measuring Performance

To measure import time improvement:

```bash
python -X importtime -c "import planfile" 2> import_time.log
less import_time.log
```

## Expected Improvements

- **Startup time**: 50-70% faster due to lazy loading
- **Repeated operations**: 80-90% faster due to caching
- **Example execution**: No more indefinite hangs
- **Memory usage**: Controlled with cache size limits

## Future Considerations

These optimizations focus on common CLI usage patterns. For server/long-running processes, consider:
- Increasing cache size limits
- Implementing persistent cache warming
- Adding performance metrics collection
