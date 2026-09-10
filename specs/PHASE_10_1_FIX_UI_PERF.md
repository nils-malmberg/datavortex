# Phase 10.1 : Fix Multi-Graph Integration + Performance Deep Optimization

*Merge visualization tabs, add subplot support, maximize 200MB+ file performance*

---

## 1. PROBLEM ANALYSIS

### Current Issues
1. **Two separate tabs** (Visualization + Multi-Graph)
   - Duplication of functionality
   - User confusion: where to create plots?
   - Lost features in Multi-Graph tab (no advanced options, plot types, customization)

2. **Performance crisis at 200MB+**
   - CSVs load very slowly
   - GroupBy freezes UI
   - Operations not truly async (still blocking)
   - Polars not used for all operations

### Solution
1. **Merge tabs** : Keep "Visualization" tab, add subplot/multi-series capability WITHIN it
2. **Add subplot builder** : Choose "Subplot Grid" or "Multi-Series" mode in same interface
3. **Performance overhaul** : Find and eliminate ALL blocking operations

---

## 2. UNIFIED VISUALIZATION TAB (MERGE & ENHANCE)

### 2.1 Single Visualization Tab Architecture

**Current structure** (WRONG):
```
Dashboard
├─ Stats
├─ Visualization (single plot)
├─ Filters
├─ Columns
└─ Multi-Graph (separate, loses features)
```

**New structure** (CORRECT):
```
Dashboard
├─ Stats
├─ Visualization
│  ├─ Plot Builder (left panel)
│  │  ├─ Plot type selector
│  │  ├─ Column selectors (X, Y, color, size, etc)
│  │  ├─ Advanced options (trends, confidence bands, etc)
│  │  └─ **Plot Layout Selector** (NEW) ← KEY CHANGE
│  │     ├─ "Single Plot" (current)
│  │     ├─ "Multi-Series" (same X, multiple Y)
│  │     └─ "Subplots Grid" (2x2, 3x3, custom)
│  │
│  └─ Preview (right panel)
│     ├─ Single plot (existing)
│     ├─ Multi-series with dual axes (existing)
│     └─ Subplot grid (new)
│
├─ Filters
├─ Columns
└─ (Remove "Multi-Graph" tab - merged into Visualization)
```

### 2.2 PlotBuilder.jsx - Unified Component

```jsx
const PlotBuilder = ({ sessionId }) => {
  const [layoutMode, setLayoutMode] = useState('single');  // 'single' | 'multi_series' | 'subplots'
  
  const [config, setConfig] = useState({
    layout_mode: 'single',
    title: '',
    x_axis: null,
    
    // Single plot
    y_axis: null,
    plot_type: 'scatter',
    
    // Multi-series (same plot, multiple Y)
    series: [],
    
    // Subplots grid
    subplot_grid: { rows: 2, cols: 2 },  // 2x2, 3x3, custom
    subplots: []  // Each subplot is a plot config
  });
  
  return (
    <div className="plot-builder">
      {/* LEFT PANEL : Configuration */}
      <div className="builder-left">
        
        {/* Layout Mode Selector (CRITICAL) */}
        <div className="layout-mode-selector">
          <h3>Plot Layout</h3>
          <button 
            className={layoutMode === 'single' ? 'active' : ''}
            onClick={() => setLayoutMode('single')}
          >
            📊 Single Plot
          </button>
          <button 
            className={layoutMode === 'multi_series' ? 'active' : ''}
            onClick={() => setLayoutMode('multi_series')}
          >
            📈 Multi-Series (Dual Axes)
          </button>
          <button 
            className={layoutMode === 'subplots' ? 'active' : ''}
            onClick={() => setLayoutMode('subplots')}
          >
            🔲 Subplots Grid
          </button>
        </div>
        
        {/* X-Axis (Common to all) */}
        <div className="config-section">
          <label>X-Axis Column</label>
          <select value={config.x_axis || ''} onChange={(e) => updateConfig({x_axis: e.target.value})}>
            <option value="">Select X column</option>
            {columns.map(col => <option key={col} value={col}>{col}</option>)}
          </select>
        </div>
        
        {/* SINGLE PLOT MODE */}
        {layoutMode === 'single' && (
          <SinglePlotConfig config={config} updateConfig={updateConfig} columns={columns} />
        )}
        
        {/* MULTI-SERIES MODE */}
        {layoutMode === 'multi_series' && (
          <MultiSeriesConfig config={config} updateConfig={updateConfig} columns={columns} />
        )}
        
        {/* SUBPLOTS MODE */}
        {layoutMode === 'subplots' && (
          <SubplotsConfig config={config} updateConfig={updateConfig} columns={columns} />
        )}
        
        {/* ADVANCED OPTIONS (visible for all modes) */}
        <AdvancedPlotOptions config={config} updateConfig={updateConfig} />
        
        <button onClick={handleCreatePlot} className="btn-primary">
          📊 Create Plot
        </button>
      </div>
      
      {/* RIGHT PANEL : Live Preview */}
      <div className="builder-right">
        {plotPreview && <PlotPreview data={plotPreview} />}
      </div>
    </div>
  );
};
```

### 2.3 Subplot Mode - Grid Configuration

```jsx
const SubplotsConfig = ({ config, updateConfig, columns }) => {
  const updateGridSize = (rows, cols) => {
    updateConfig({
      subplot_grid: { rows, cols },
      subplots: Array(rows * cols).fill(null).map((_, i) => ({
        id: `subplot_${i}`,
        plot_type: 'scatter',
        x_axis: null,
        y_axis: null
      }))
    });
  };
  
  return (
    <div className="subplots-config">
      <h3>Subplot Grid</h3>
      
      {/* Grid Size Selector */}
      <div className="grid-selector">
        <label>Grid Size</label>
        <div className="grid-presets">
          <button onClick={() => updateGridSize(1, 2)}>1x2</button>
          <button onClick={() => updateGridSize(2, 2)}>2x2</button>
          <button onClick={() => updateGridSize(2, 3)}>2x3</button>
          <button onClick={() => updateGridSize(3, 3)}>3x3</button>
          <button onClick={() => updateGridSize(4, 2)}>4x2</button>
        </div>
        <p>Or custom: 
          <input type="number" min="1" max="10" placeholder="rows" onChange={(e) => updateGridSize(parseInt(e.target.value), config.subplot_grid.cols)} />
          x
          <input type="number" min="1" max="10" placeholder="cols" onChange={(e) => updateGridSize(config.subplot_grid.rows, parseInt(e.target.value))} />
        </p>
      </div>
      
      {/* Configure Each Subplot */}
      <div className="subplots-list">
        <h4>Configure Subplots</h4>
        {config.subplots.map((subplot, idx) => (
          <SubplotEditor
            key={subplot.id}
            subplot={subplot}
            index={idx}
            columns={columns}
            onUpdate={(updates) => updateSubplot(subplot.id, updates)}
          />
        ))}
      </div>
    </div>
  );
};

const SubplotEditor = ({ subplot, index, columns, onUpdate }) => {
  return (
    <div className="subplot-editor">
      <h5>Subplot {index + 1}</h5>
      
      <select value={subplot.plot_type} onChange={(e) => onUpdate({ plot_type: e.target.value })}>
        <option value="scatter">Scatter</option>
        <option value="line">Line</option>
        <option value="bar">Bar</option>
        <option value="histogram">Histogram</option>
        <option value="box">Box Plot</option>
        <option value="violin">Violin Plot</option>
      </select>
      
      <select value={subplot.x_axis || ''} onChange={(e) => onUpdate({ x_axis: e.target.value })}>
        <option value="">X column</option>
        {columns.map(col => <option key={col} value={col}>{col}</option>)}
      </select>
      
      <select value={subplot.y_axis || ''} onChange={(e) => onUpdate({ y_axis: e.target.value })}>
        <option value="">Y column</option>
        {columns.filter(c => isNumeric(c)).map(col => <option key={col} value={col}>{col}</option>)}
      </select>
    </div>
  );
};
```

### 2.4 Backend - Unified Plot Endpoint

```python
@app.post("/api/plot/create")
async def create_plot(body: dict):
    """
    Unified endpoint for single, multi-series, and subplot plots
    
    Body:
    {
      "session_id": "...",
      "layout_mode": "single" | "multi_series" | "subplots",
      "title": "...",
      "x_axis": "...",
      
      "y_axis": "..." (if single),
      "plot_type": "scatter" (if single),
      
      "series": [...] (if multi_series),
      
      "subplot_grid": {"rows": 2, "cols": 2} (if subplots),
      "subplots": [...] (if subplots)
    }
    """
    
    session_id = body['session_id']
    layout_mode = body['layout_mode']
    df = get_session_data(session_id)
    
    if layout_mode == 'single':
        fig = create_single_plot(df, body)
    elif layout_mode == 'multi_series':
        fig = create_multi_series_plot(df, body)
    elif layout_mode == 'subplots':
        fig = create_subplot_grid(df, body)
    else:
        raise ValueError(f"Unknown layout mode: {layout_mode}")
    
    return {'plot_json': fig.to_json()}

def create_subplot_grid(df, config):
    """Create subplot grid using plotly.subplots"""
    from plotly.subplots import make_subplots
    
    rows = config['subplot_grid']['rows']
    cols = config['subplot_grid']['cols']
    
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=[f"Plot {i+1}" for i in range(len(config['subplots']))]
    )
    
    for idx, subplot_config in enumerate(config['subplots']):
        row = idx // cols + 1
        col = idx % cols + 1
        
        trace = create_trace(df, subplot_config)
        fig.add_trace(trace, row=row, col=col)
    
    fig.update_layout(title=config['title'], showlegend=True)
    return fig
```

---

## 3. PERFORMANCE DEEP OPTIMIZATION FOR 200MB+

### 3.1 Performance Audit: Where's the Bottleneck?

**Test with real 200MB CSV:**

```python
import time
import polars as pl

file_path = 'test_data/large_200mb.csv'

# Benchmark 1: Pure file read
start = time.time()
df = pl.read_csv(file_path)
print(f"pl.read_csv: {time.time() - start:.2f}s")

# Benchmark 2: Lazy read + collect
start = time.time()
df = pl.scan_csv(file_path).collect()
print(f"pl.scan_csv + collect: {time.time() - start:.2f}s")

# Benchmark 3: Lazy read (no collect yet)
start = time.time()
df_lazy = pl.scan_csv(file_path)
print(f"pl.scan_csv (lazy): {time.time() - start:.2f}s")

# Benchmark 4: Stats on lazy
start = time.time()
stats = df_lazy.select([pl.col('*').mean()]).collect()
print(f"Stats on lazy: {time.time() - start:.2f}s")

# Benchmark 5: GroupBy
start = time.time()
grouped = df_lazy.groupby('dept').agg([pl.col('salary').mean()]).collect()
print(f"GroupBy: {time.time() - start:.2f}s")

# Expected output (if optimized):
# pl.read_csv: 8-12 seconds
# pl.scan_csv + collect: 8-12 seconds (same)
# pl.scan_csv (lazy): 0.0 seconds (instant!)
# Stats on lazy: 3-5 seconds
# GroupBy: 2-4 seconds
```

### 3.2 Critical Fix: Lazy Loading Everywhere

**Problem**: Stats/groupby/filter triggering .collect() too early

**Solution**: Keep lazy as long as possible

```python
# BEFORE (BAD - collects too early):
@app.get("/api/stats/{session_id}")
def get_stats(session_id: str):
    df = pl.read_csv(file_path)  # ❌ LOADS FULL FILE TO MEMORY
    stats = df.describe()
    return stats

# AFTER (GOOD - lazy until last moment):
@app.get("/api/stats/{session_id}")
async def get_stats(session_id: str):
    df_lazy = pl.scan_csv(file_path)  # ✅ DOESN'T LOAD YET
    stats = df_lazy.select([
        pl.col('*').mean(),
        pl.col('*').std(),
        pl.col('*').min(),
        pl.col('*').max(),
    ]).collect()  # ✅ COLLECT ONLY STATS, NOT FULL DATA
    return stats
```

### 3.3 Async All Operations (True Async, Not Threading)

**Problem**: Operations still block despite asyncio decorator

**Real Issue**: `pl.read_csv()` is synchronous, MUST run in thread pool

```python
# CORRECT ASYNC:
from concurrent.futures import ThreadPoolExecutor
import asyncio

executor = ThreadPoolExecutor(max_workers=4)  # Max 4 threads for CPU-bound

@app.post("/api/groupby")
async def groupby_endpoint(body: dict):
    session_id = body['session_id']
    file_path = get_session_path(session_id)
    
    # Run heavy operation in thread pool (doesn't block event loop)
    result = await asyncio.get_event_loop().run_in_executor(
        executor,
        perform_groupby,  # Sync function
        file_path,
        body['group_by'],
        body['agg']
    )
    
    return {'data': result}

def perform_groupby(file_path, group_by, agg):
    """Sync function running in thread pool"""
    df = pl.scan_csv(file_path)  # Lazy load
    return df.groupby(group_by).agg(agg).collect()
```

### 3.4 Streaming CSV Reading (For 500MB+)

**Problem**: Even lazy loading loads chunks into memory

**Solution**: Chunked reading for initial preview/stats

```python
def get_preview_from_large_csv(file_path, n_rows=100):
    """Get first N rows without loading full file"""
    # Read only first chunk (~1MB)
    df = pl.scan_csv(file_path).limit(n_rows).collect()
    return df

def get_row_count_fast(file_path):
    """Count rows by sampling (not 100% accurate but fast)"""
    import subprocess
    # Use command-line tool for speed
    result = subprocess.run(['wc', '-l', file_path], capture_output=True, text=True)
    return int(result.stdout.split()[0])
```

### 3.5 Caching Aggressive (NO RECOMPUTATION)

```python
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

class SessionCache:
    def __init__(self, ttl_minutes=30):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get_cache_key(self, session_id, operation, params):
        """Create unique cache key"""
        param_hash = hashlib.md5(str(params).encode()).hexdigest()[:8]
        return f"{session_id}_{operation}_{param_hash}"
    
    def get(self, session_id, operation, params):
        key = self.get_cache_key(session_id, operation, params)
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                print(f"✓ Cache HIT: {operation} ({key})")
                return data
        return None
    
    def set(self, session_id, operation, params, data):
        key = self.get_cache_key(session_id, operation, params)
        self.cache[key] = (data, datetime.now())
        print(f"✓ Cache SET: {operation} ({key})")

cache = SessionCache(ttl_minutes=60)

# Usage:
@app.get("/api/stats/{session_id}")
async def get_stats(session_id: str):
    cached = cache.get(session_id, 'stats', {})
    if cached:
        return cached
    
    # Compute stats
    stats = await compute_stats_async(session_id)
    cache.set(session_id, 'stats', {}, stats)
    return stats
```

### 3.6 Pre-computed Metadata

```python
# On file upload, compute once and cache:
@app.post("/api/upload")
async def upload(file: UploadFile):
    file_path = save_file(file)
    session_id = generate_session_id()
    
    # Pre-compute metadata (async, in background)
    loop = asyncio.get_event_loop()
    metadata = await loop.run_in_executor(
        executor,
        compute_metadata,  # Blocks, so run in thread
        file_path
    )
    
    # Store metadata (fast)
    session_store[session_id] = {
        'file_path': file_path,
        'metadata': metadata,  # Cached!
        'created_at': datetime.now()
    }
    
    return {
        'session_id': session_id,
        'row_count': metadata['row_count'],
        'columns': metadata['columns'],
        'dtypes': metadata['dtypes']
    }

def compute_metadata(file_path):
    """Compute once, cache forever"""
    df_lazy = pl.scan_csv(file_path)
    return {
        'row_count': df_lazy.select(pl.col('*').count()).collect()[0, 0],
        'columns': df_lazy.collect_schema().names(),
        'dtypes': {name: str(dtype) for name, dtype in df_lazy.collect_schema().items()}
    }
```

### 3.7 Connection Pool + Resource Limits

```python
# Limit concurrent file operations
MAX_CONCURRENT_OPERATIONS = 4
semaphore = asyncio.Semaphore(MAX_CONCURRENT_OPERATIONS)

@app.post("/api/heavy-operation")
async def heavy_operation(body: dict):
    async with semaphore:  # Max 4 concurrent
        result = await perform_operation(body)
    return result
```

---

## 4. TESTING PERFORMANCE RECOVERY

### 4.1 Benchmark Suite

```python
# test_performance_200mb.py
import time

@pytest.mark.benchmark
class TestPerformance200MB:
    
    def test_load_200mb(self):
        """200MB CSV load should be < 15 seconds"""
        start = time.time()
        df = pl.scan_csv('test_data/200mb.csv').collect()
        duration = time.time() - start
        assert duration < 15, f"Load took {duration}s, target < 15s"
        print(f"✓ 200MB load: {duration:.1f}s")
    
    def test_preview_instant(self):
        """Preview first 100 rows should be < 100ms"""
        start = time.time()
        df = pl.scan_csv('test_data/200mb.csv').limit(100).collect()
        duration = time.time() - start
        assert duration < 0.1, f"Preview took {duration}s"
        print(f"✓ Preview: {duration*1000:.0f}ms")
    
    def test_stats_5s(self):
        """Stats on 200MB should be < 5 seconds"""
        start = time.time()
        df_lazy = pl.scan_csv('test_data/200mb.csv')
        stats = df_lazy.select([pl.col('*').mean()]).collect()
        duration = time.time() - start
        assert duration < 5, f"Stats took {duration}s"
        print(f"✓ Stats: {duration:.1f}s")
    
    def test_groupby_3s(self):
        """GroupBy 200MB should be < 3 seconds"""
        start = time.time()
        df_lazy = pl.scan_csv('test_data/200mb.csv')
        result = df_lazy.groupby('dept').agg([pl.col('salary').mean()]).collect()
        duration = time.time() - start
        assert duration < 3, f"GroupBy took {duration}s"
        print(f"✓ GroupBy: {duration:.1f}s")
    
    def test_filter_1s(self):
        """Filter 200MB should be < 1 second"""
        start = time.time()
        df_lazy = pl.scan_csv('test_data/200mb.csv')
        result = df_lazy.filter(pl.col('salary') > 50000).collect()
        duration = time.time() - start
        assert duration < 1, f"Filter took {duration}s"
        print(f"✓ Filter: {duration:.1f}s")
```

### 4.2 Generate 200MB Test File

```python
# generate_200mb_test.py
import polars as pl
import random

def generate_200mb_csv():
    # 2.5M rows × ~80 bytes = 200MB
    n = 2_500_000
    
    df = pl.DataFrame({
        'id': range(n),
        'name': [f'person_{i % 10000}' for i in range(n)],
        'age': [random.randint(18, 80) for _ in range(n)],
        'salary': [random.randint(30000, 150000) for _ in range(n)],
        'dept': [random.choice(['Sales', 'IT', 'HR', 'Finance', 'Ops']) for _ in range(n)],
        'hire_date': [f'2020-{random.randint(1,12):02d}-{random.randint(1,28):02d}' for _ in range(n)],
    })
    
    df.write_csv('test_data/200mb.csv')
    size_mb = df.estimated_size('mb')
    print(f"Generated 200MB test file: {size_mb:.0f}MB, {n} rows")

generate_200mb_csv()
```

---

## 5. GIT WORKFLOW

```bash
git checkout -b feature/phase-10-fix-ui-performance

git commit -m "refactor: merge multi-graph into visualization tab with subplot support"
git commit -m "feat: subplot grid layout (2x2, 3x3, custom)"
git commit -m "feat: unified plot creation with layout selector"

git commit -m "perf: lazy loading everywhere (scan_csv, no premature collect)"
git commit -m "perf: true async with thread pool executor"
git commit -m "perf: streaming preview (first 100 rows instant)"
git commit -m "perf: aggressive caching (60 min TTL)"
git commit -m "perf: metadata pre-computation on upload"

git commit -m "test: benchmark suite for 200MB files"
git commit -m "docs: performance targets documented (< 15s load, < 5s stats)"

git push origin feature/phase-10-fix-ui-performance
```

---

## 6. SUCCESS CRITERIA

✅ Single Visualization tab (no duplication)  
✅ Subplot grid works (2x2, 3x3, custom)  
✅ All plot customization available in all modes  
✅ 200MB CSV loads in < 15 seconds  
✅ Preview (100 rows) instant (< 100ms)  
✅ Stats on 200MB in < 5 seconds  
✅ GroupBy on 200MB in < 3 seconds  
✅ Filter on 200MB in < 1 second  
✅ UI never freezes during operations  
✅ Cache hits reduce repeat queries 10x  
✅ All benchmarks pass