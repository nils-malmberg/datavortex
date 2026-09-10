# Phase 9 : Performance Optimization for Large Datasets

*Transform DataVortex to handle 100k+ rows and 500MB+ files efficiently*

---

## 1. PROBLEM STATEMENT

### Current Issues
- Pandas loads entire CSV into RAM (memory inefficient)
- Operations (groupby, filter, plot) block UI (no async)
- No pagination or lazy loading for large datasets
- Frontend virtualizes tables but backend sends all rows
- GroupBy on 500k+ rows : multiple seconds delay
- Export large datasets : memory spike, browser freeze

### Target
- ✅ Handle 500MB+ files smoothly
- ✅ Sub-second UI response (groupby, filter, plot)
- ✅ Zero freezing on large operations
- ✅ Memory footprint < 2GB for 500MB files
- ✅ Streaming exports (no memory spike)

---

## 2. BACKEND OPTIMIZATION : PANDAS → POLARS

### 2.1 Why Polars?

| Feature | Pandas | Polars |
|---------|--------|--------|
| Speed | Slow (row-based) | 10-100x faster (columnar) |
| Memory | High | 2-10x lower |
| Lazy eval | No | Yes (query optimization) |
| Streaming | No | Yes |
| Parallel | Limited | Full multi-core |
| Null handling | Inconsistent | Consistent |
| String ops | Slow | Fast |
| GroupBy | Slow | Very fast |

**Decision**: Migrate from Pandas to Polars for all data operations.

### 2.2 Migration Strategy

**Phase 1 : Dual support (Pandas + Polars)**
- Keep pandas for compatibility
- Add polars for large files (> 50MB)
- Auto-switch based on file size

**Phase 2 : Full migration to Polars**
- Remove pandas dependency
- Update all routes

### 2.3 Backend Changes (app/data_service.py)

```python
import polars as pl
from pathlib import Path

class DataService:
    def __init__(self, use_polars=True):
        self.use_polars = use_polars
    
    def load_file(self, file_path: str) -> pl.DataFrame | pd.DataFrame:
        """
        Load CSV/Excel with smart format selection
        - Files > 50MB : use Polars (lazy loading)
        - Files < 50MB : use Pandas (compatibility)
        """
        file_size = Path(file_path).stat().st_size
        
        if self.use_polars and file_size > 50_000_000:  # 50MB
            # Lazy load with Polars
            return pl.scan_csv(file_path)  # Lazy, no execution yet
        else:
            # Fallback to Pandas
            return pd.read_csv(file_path)
    
    def get_preview(self, df, n_rows=100):
        """Get first N rows without loading full dataset"""
        if isinstance(df, pl.LazyFrame):
            return df.limit(n_rows).collect()  # Execute only first N
        elif isinstance(df, pl.DataFrame):
            return df.head(n_rows)
        else:  # Pandas
            return df.head(n_rows)
    
    def get_stats(self, df):
        """Compute stats without loading full dataset (lazy execution)"""
        if isinstance(df, pl.LazyFrame):
            # Lazy eval - doesn't touch disk until collect()
            stats = df.select([
                pl.col("*").count().alias("count"),
                pl.col("*").mean().alias("mean"),
                pl.col("*").std().alias("std"),
                pl.col("*").min().alias("min"),
                pl.col("*").max().alias("max"),
            ]).collect()  # Execute once here
            return stats
        else:
            # Pandas fallback
            return df.describe()
    
    def apply_filter(self, df, filters: dict):
        """Apply filters lazily (deferred execution)"""
        if isinstance(df, pl.LazyFrame):
            # Build filter chain (no execution yet)
            for col, condition in filters.items():
                if condition['op'] == 'gt':
                    df = df.filter(pl.col(col) > condition['value'])
                elif condition['op'] == 'lt':
                    df = df.filter(pl.col(col) < condition['value'])
                elif condition['op'] == 'contains':
                    df = df.filter(pl.col(col).str.contains(condition['value']))
                # ... more conditions
            return df  # Still lazy!
        else:
            # Pandas fallback
            return apply_pandas_filters(df, filters)
    
    def groupby(self, df, group_by: list, agg: dict):
        """GroupBy with lazy execution"""
        if isinstance(df, pl.LazyFrame):
            # Lazy groupby (deferred, optimized)
            return df.groupby(group_by).agg([
                pl.col(col).mean().alias(f"{col}_mean")
                for col in agg.get('mean', [])
            ]).collect()  # Execute only when needed
        else:
            # Pandas fallback
            return df.groupby(group_by).agg(agg)
```

### 2.4 Async Operations (app/async_service.py)

All heavy operations run async (don't block UI):

```python
from fastapi import BackgroundTasks
import asyncio

class AsyncDataService:
    """
    Run heavy operations in background
    Client polls for results
    """
    
    def __init__(self):
        self.tasks = {}  # {task_id -> result}
    
    async def groupby_async(self, session_id: str, group_by: list, agg: dict) -> str:
        """
        Start groupby in background
        Return task_id immediately
        """
        task_id = generate_id()
        
        async def run_groupby():
            df = get_session_data(session_id)
            result = df.groupby(group_by).agg(agg).collect()
            self.tasks[task_id] = {
                'status': 'done',
                'data': result,
                'timestamp': datetime.now()
            }
        
        asyncio.create_task(run_groupby())
        return task_id  # Return immediately
    
    async def get_task_result(self, task_id: str):
        """Poll for task result (client asks this repeatedly)"""
        task = self.tasks.get(task_id)
        if not task:
            return {'status': 'not_found'}
        if task['status'] == 'done':
            return {'status': 'done', 'data': task['data']}
        else:
            return {'status': 'pending'}
```

### 2.5 Streaming Exports

```python
from fastapi.responses import StreamingResponse

async def export_csv_streaming(session_id: str):
    """
    Stream CSV without loading full file in RAM
    Send chunks of 10k rows at a time
    """
    df = get_session_data(session_id)
    
    async def generate():
        if isinstance(df, pl.LazyFrame):
            # Chunk processing
            chunk_size = 10_000
            for chunk in df.collect_partitions():
                yield chunk.write_csv() + b'\n'
        else:
            for chunk in pd.read_csv(file, chunksize=10_000):
                yield chunk.to_csv(index=False).encode()
    
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"}
    )
```

### 2.6 dependencies

Update `backend/pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "polars[parquet,excel,csv]==0.20.0",  # ✅ NEW - Polars (replace pandas)
    "pandas==2.1.0",  # Keep for compatibility
    "numpy==1.24.0",
    "scipy==1.11.0",
    "plotly==5.17.0",
    "scikit-learn==1.3.2",
    "torch>=2.0.0",  # PyTorch (not TensorFlow)
    "python-multipart==0.0.6",
    "chardet==5.2.0",
    "reportlab==4.0.0",
    "weasyprint==59.0",
    "python-dateutil==2.8.2",
    "httpx==0.25.0",  # For async HTTP
]
```

---

## 3. FRONTEND OPTIMIZATION

### 3.1 Intelligent Pagination

**DataPreview.jsx** - Never load all rows:

```jsx
const DataPreview = ({ sessionId }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 100;  // Load 100 rows at a time
  const [totalRows, setTotalRows] = useState(null);
  
  useEffect(() => {
    // Fetch first page + total count
    fetch(`/api/data/${sessionId}/preview?page=1&size=100&count_total=true`)
      .then(res => res.json())
      .then(data => {
        setRows(data.rows);
        setTotalRows(data.total);  // Total without loading all
      });
  }, [sessionId]);
  
  const handlePageChange = (page) => {
    // Fetch specific page only
    fetch(`/api/data/${sessionId}/preview?page=${page}&size=100`)
      .then(res => res.json())
      .then(data => setRows(data.rows));
  };
  
  return (
    <>
      <table>
        {/* Display only current page rows */}
        {rows.map(row => <tr key={row.id}>{/* ... */}</tr>)}
      </table>
      
      <Pagination 
        currentPage={currentPage}
        totalPages={Math.ceil(totalRows / pageSize)}
        onPageChange={handlePageChange}
      />
    </>
  );
};
```

### 3.2 Async Task Status (UI doesn't freeze)

```jsx
const GroupByAnalysis = ({ sessionId }) => {
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  
  const handleCompute = async () => {
    setStatus('loading');
    
    // Start task in background, get task_id immediately
    const res = await fetch('/api/groupby/async', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, group_by, agg })
    });
    const { task_id } = await res.json();
    setTaskId(task_id);
    
    // Poll for result (with exponential backoff)
    let interval = 500;
    while (true) {
      await new Promise(r => setTimeout(r, interval));
      
      const pollRes = await fetch(`/api/tasks/${task_id}`);
      const pollData = await pollRes.json();
      
      if (pollData.status === 'done') {
        setResult(pollData.data);
        setStatus('done');
        break;
      }
      
      interval = Math.min(interval * 1.2, 3000);  // Exponential backoff
    }
  };
  
  return (
    <>
      <button onClick={handleCompute} disabled={status === 'loading'}>
        {status === 'loading' ? '⏳ Computing...' : 'Compute GroupBy'}
      </button>
      {status === 'loading' && <ProgressBar />}
      {result && <ResultTable data={result} />}
    </>
  );
};
```

### 3.3 Virtual Scrolling (Already exists, but optimize)

Use `react-window` or `react-virtualized` for 1M+ rows display:

```jsx
import { FixedSizeList } from 'react-window';

const DataTable = ({ rows, columns }) => {
  const Row = ({ index, style }) => (
    <div style={style} className="table-row">
      {columns.map(col => <div key={col}>{rows[index][col]}</div>)}
    </div>
  );
  
  return (
    <FixedSizeList
      height={600}
      itemCount={rows.length}
      itemSize={35}
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
};
```

### 3.4 Debouncing & Throttling

All expensive operations debounced:

```jsx
// Debounce filter input (wait 500ms after user stops typing)
const handleFilterChange = useCallback(
  debounce((filter) => {
    fetch(`/api/filters/apply`, { body: JSON.stringify({filter}) });
  }, 500),
  []
);

// Throttle scroll events (max once per 100ms)
const handleScroll = useCallback(
  throttle(() => {
    // Load more rows
  }, 100),
  []
);
```

### 3.5 Lazy Plot Loading

```jsx
const PlotBuilder = ({ sessionId }) => {
  const [plotData, setPlotData] = useState(null);
  const [isLoadingPlot, setIsLoadingPlot] = useState(false);
  
  const handleCreatePlot = async () => {
    setIsLoadingPlot(true);
    
    // Request plot (server computes in background)
    const res = await fetch(`/api/plot/create`, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, plot_config })
    });
    
    // Stream response as data arrives
    const reader = res.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const partial = JSON.parse(new TextDecoder().decode(value));
      setPlotData(partial);  // Update UI incrementally
    }
    
    setIsLoadingPlot(false);
  };
  
  return (
    <>
      <button onClick={handleCreatePlot}>Create Plot</button>
      {isLoadingPlot && <Spinner />}
      {plotData && <Plot data={plotData} />}
    </>
  );
};
```

---

## 4. DATABASE CONSIDERATIONS (Future)

For very large datasets (GB+), consider:
- **DuckDB** : SQL engine optimized for analytics (in-process)
- **ClickHouse** : Cloud analytics database
- **TimescaleDB** : For time-series data

For now: Polars is sufficient for 500MB-1GB files.

---

## 5. CACHING & MEMOIZATION

### 5.1 Backend Caching

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, ttl_seconds=300):  # 5 min TTL
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, datetime.now())

cache_mgr = CacheManager()

# Cache stats (they don't change if data unchanged)
@app.get("/api/stats/{session_id}")
def get_stats(session_id: str):
    cache_key = f"stats_{session_id}"
    cached = cache_mgr.get(cache_key)
    if cached:
        return cached
    
    df = get_session_data(session_id)
    stats = compute_stats(df)
    cache_mgr.set(cache_key, stats)
    return stats
```

### 5.2 Frontend Memoization (React.memo, useMemo)

```jsx
const DataPreview = React.memo(({ data }) => {
  const memoizedRows = useMemo(() => 
    data.filter(row => !row.deleted),
    [data]
  );
  
  return <Table rows={memoizedRows} />;
});
```

---

## 6. MONITORING & DIAGNOSTICS

### 6.1 Performance Metrics

Add to each API response:

```python
import time

@app.post("/api/groupby")
async def groupby_endpoint(body: dict):
    start = time.time()
    
    result = await perform_groupby(body)
    
    duration = time.time() - start
    
    return {
        'data': result,
        'metrics': {
            'duration_seconds': duration,
            'rows_processed': len(result),
            'throughput_rows_per_sec': len(result) / duration
        }
    }
```

Frontend displays in UI:
```
✓ GroupBy computed in 1.2s (50k rows, 41k rows/sec)
```

### 6.2 Memory Monitoring

```python
import psutil

def get_memory_usage():
    process = psutil.Process()
    return {
        'rss_mb': process.memory_info().rss / 1024 / 1024,  # Resident
        'vms_mb': process.memory_info().vms / 1024 / 1024   # Virtual
    }

# Log every minute
@app.get("/api/health")
def health():
    return {
        'status': 'ok',
        'memory': get_memory_usage(),
        'uptime_seconds': time.time() - start_time
    }
```

---

## 7. TESTING WITH LARGE FILES

### 7.1 Generate Test Datasets

```python
# generate_test_data.py
import polars as pl
import random

def generate_large_csv(filename, n_rows=500_000):
    """Generate 500k row CSV (50-100MB)"""
    df = pl.DataFrame({
        'id': range(n_rows),
        'name': [f"user_{i}" for i in range(n_rows)],
        'age': [random.randint(18, 80) for _ in range(n_rows)],
        'salary': [random.randint(30000, 150000) for _ in range(n_rows)],
        'department': [random.choice(['Sales', 'IT', 'HR', 'Finance']) for _ in range(n_rows)],
        'date': [f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}" for _ in range(n_rows)],
    })
    df.write_csv(filename)
    print(f"Generated {filename} ({Path(filename).stat().st_size / 1024 / 1024:.1f}MB)")

# Run
generate_large_csv('test_data/large_500k.csv', 500_000)
```

### 7.2 Benchmarks

```python
# test_performance.py
import time
import polars as pl

df = pl.scan_csv('test_data/large_500k.csv')

# Benchmark 1: Stats
start = time.time()
stats = df.select([pl.col('*').mean()]).collect()
print(f"Stats: {time.time() - start:.2f}s")

# Benchmark 2: GroupBy
start = time.time()
grouped = df.groupby('department').agg([pl.col('salary').mean()]).collect()
print(f"GroupBy: {time.time() - start:.2f}s")

# Benchmark 3: Filter
start = time.time()
filtered = df.filter(pl.col('age') > 30).collect()
print(f"Filter: {time.time() - start:.2f}s")

# Expected output:
# Stats: 0.15s
# GroupBy: 0.08s
# Filter: 0.12s
```

---

## 8. DEPLOYMENT NOTES

### 8.1 Memory Limits

For 500MB files, allocate:
- Min RAM: 4GB
- Recommended: 8GB+

```bash
# Limit DataVortex memory (if needed)
# Linux/macOS:
PYTHONHASHSEED=0 python -m datavortex.cli

# Windows:
set PYTHONHASHSEED=0
python -m datavortex.cli
```

### 8.2 Disk Usage

Temporary files during operations:
- CSV parsing cache: 100-200MB
- Plot generation: 50-100MB
- Clean up after operations

Ensure disk has >= 1GB free.

---

## 9. IMPLEMENTATION ROADMAP

### Phase 9a : Polars Migration (Backend)
- [ ] Install Polars
- [ ] Update data_service.py (dual pandas/polars)
- [ ] Update all routes (stats, filter, groupby, etc)
- [ ] Test with large CSV (500k rows)
- [ ] Benchmark vs pandas

### Phase 9b : Async Operations
- [ ] Implement async task system
- [ ] Update routes (groupby, export, ML)
- [ ] Frontend: task polling UI
- [ ] Loading spinners + progress

### Phase 9c : Frontend Optimization
- [ ] Pagination (100 rows/page)
- [ ] Virtual scrolling
- [ ] Debouncing filters
- [ ] Lazy plot loading
- [ ] Streaming exports

### Phase 9d : Testing & Monitoring
- [ ] Generate test datasets (500k rows)
- [ ] Performance benchmarks
- [ ] Memory monitoring
- [ ] Health check endpoint
- [ ] Documentation

---

## 10. SUCCESS CRITERIA

✅ 500MB+ files load in < 5 seconds
✅ GroupBy on 500k rows in < 1 second
✅ Filters apply in < 500ms
✅ UI never freezes (async all operations)
✅ Memory usage < 2GB for 500MB file
✅ Export large files without spike
✅ Plots render without delay
✅ Pagination smooth & fast
✅ Benchmarks documented
✅ v1.0.0 → v1.1 release notes updated

---

## 11. GIT WORKFLOW

```bash
# Create new branch
git checkout -b feature/performance-optimization-polars

# Work on optimizations
# Commit frequently:
git commit -m "feat: replace pandas with polars for large files"
git commit -m "feat: async operations to prevent UI freeze"
git commit -m "feat: pagination for data preview"
git commit -m "feat: streaming exports"
git commit -m "test: performance benchmarks with 500k row dataset"

# Push to GitHub
git push origin feature/performance-optimization-polars

# Create PR (pull request)
# Title: "Performance Optimization: Polars Migration & Async Operations"
# Description: Include benchmark results, improvements
```