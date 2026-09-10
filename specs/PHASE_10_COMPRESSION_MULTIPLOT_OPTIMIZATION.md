# Phase 10 : Compressed Formats + Multi-Plot Visualization + Advanced Optimization

*Add compressed input support, multi-series plots with dual axes, and maximize performance for TB+ scale*

---

## 1. COMPRESSED FORMAT SUPPORT

### 1.1 Supported Formats

**Current** : CSV, Excel, JSON, Parquet
**Add** :
- CSV.GZ (gzip compressed)
- CSV.BZ2 (bzip2)
- CSV.ZIP (zip archive)
- Parquet.GZ
- PARQUET.SNAPPY (Parquet with Snappy compression)
- PARQUET.ZSTD (Parquet with Zstandard)
- Feather (Arrow IPC format, pre-compressed)

### 1.2 Backend Implementation (app/data_service.py)

```python
import polars as pl
import gzip
import bz2
import zipfile
from pathlib import Path

class DataService:
    SUPPORTED_FORMATS = {
        '.csv': 'csv',
        '.csv.gz': 'csv_gz',
        '.csv.bz2': 'csv_bz2',
        '.csv.zip': 'csv_zip',
        '.parquet': 'parquet',
        '.parquet.gz': 'parquet_gz',
        '.parquet.snappy': 'parquet_snappy',
        '.parquet.zstd': 'parquet_zstd',
        '.feather': 'feather',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.json': 'json',
    }
    
    def detect_format(self, file_path: str) -> str:
        """Auto-detect format from filename"""
        path = Path(file_path)
        
        # Check compound extensions first (.csv.gz before .gz)
        full_name = path.name.lower()
        for ext, fmt in self.SUPPORTED_FORMATS.items():
            if full_name.endswith(ext):
                return fmt
        
        raise ValueError(f"Unsupported format: {path.suffix}")
    
    def load_file(self, file_path: str, use_polars=True) -> pl.DataFrame:
        """Load any supported format automatically"""
        fmt = self.detect_format(file_path)
        file_size = Path(file_path).stat().st_size
        
        try:
            if fmt == 'csv':
                df = pl.read_csv(file_path) if file_size < 50_000_000 else pl.scan_csv(file_path)
            
            elif fmt == 'csv_gz':
                # Auto-decompress on read
                df = pl.read_csv(file_path)  # Polars handles .gz automatically!
            
            elif fmt == 'csv_bz2':
                # Polars doesn't auto-handle bz2, manual decompress
                with bz2.open(file_path, 'rt') as f:
                    df = pl.read_csv(f)
            
            elif fmt == 'csv_zip':
                # Extract and read first CSV in archive
                with zipfile.ZipFile(file_path) as z:
                    csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                    if not csv_files:
                        raise ValueError("No CSV found in zip archive")
                    with z.open(csv_files[0]) as f:
                        df = pl.read_csv(f)
            
            elif fmt == 'parquet':
                df = pl.read_parquet(file_path)
            
            elif fmt == 'parquet_gz':
                # Parquet with gzip compression
                df = pl.read_parquet(file_path)  # Auto-handled
            
            elif fmt == 'parquet_snappy':
                df = pl.read_parquet(file_path)
            
            elif fmt == 'parquet_zstd':
                df = pl.read_parquet(file_path)
            
            elif fmt == 'feather':
                df = pl.read_ipc(file_path)  # Arrow IPC (Feather)
            
            elif fmt == 'excel':
                df = pl.read_excel(file_path)
            
            elif fmt == 'json':
                df = pl.read_json(file_path)
            
            else:
                raise ValueError(f"Format handler not implemented: {fmt}")
            
            return df
        
        except Exception as e:
            raise ValueError(f"Failed to load {fmt}: {str(e)}")
    
    def get_file_info(self, file_path: str) -> dict:
        """Return info about file (size, compression ratio, etc)"""
        path = Path(file_path)
        fmt = self.detect_format(file_path)
        size_bytes = path.stat().st_size
        size_mb = size_bytes / 1024 / 1024
        
        info = {
            'filename': path.name,
            'format': fmt,
            'size_mb': round(size_mb, 2),
            'compression': 'gzip' if 'gz' in fmt else 'zstd' if 'zstd' in fmt else 'snappy' if 'snappy' in fmt else 'none'
        }
        
        # Estimate uncompressed size (rough)
        if 'gz' in fmt or 'bz2' in fmt:
            # Typical compression ratio: 10-20% for CSV
            info['estimated_uncompressed_mb'] = round(size_mb / 0.15, 2)
        
        return info
```

### 1.3 Frontend Changes (UploadZone.jsx)

```jsx
const UploadZone = () => {
  const [fileInfo, setFileInfo] = useState(null);
  
  const handleFileUpload = async (file) => {
    // Check format
    const supportedFormats = [
      '.csv', '.csv.gz', '.csv.bz2', '.csv.zip',
      '.parquet', '.parquet.gz', '.parquet.snappy', '.parquet.zstd',
      '.feather', '.xlsx', '.xls', '.json'
    ];
    
    const isSupportedFormat = supportedFormats.some(fmt => 
      file.name.toLowerCase().endsWith(fmt)
    );
    
    if (!isSupportedFormat) {
      alert('Unsupported format. Try: CSV, CSV.GZ, Parquet, Excel, JSON');
      return;
    }
    
    // Upload
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const { session_id, format, file_info } = await res.json();
    
    // Show info
    setFileInfo({
      name: file.name,
      format: format,
      size: `${file_info.size_mb} MB`,
      compression: file_info.compression,
      estimated: file_info.estimated_uncompressed_mb
    });
    
    // Proceed with parsing
    showParserOptions(session_id, format);
  };
  
  return (
    <>
      <DragDropZone onDrop={handleFileUpload} />
      {fileInfo && (
        <div className="file-info">
          <p>📦 {fileInfo.name}</p>
          <p>Format: {fileInfo.format} ({fileInfo.compression})</p>
          <p>Size: {fileInfo.size}</p>
          {fileInfo.estimated && <p>Est. uncompressed: {fileInfo.estimated} MB</p>}
        </div>
      )}
    </>
  );
};
```

### 1.4 Route Changes (app/main.py)

```python
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Upload file in any supported format"""
    file_path = f"/tmp/{file.filename}"
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        fmt = data_service.detect_format(file_path)
        file_info = data_service.get_file_info(file_path)
        
        return {
            'session_id': generate_session_id(),
            'filename': file.filename,
            'format': fmt,
            'file_info': file_info,
            'status': 'ready_to_parse'
        }
    except Exception as e:
        return {'error': str(e)}, 400
```

---

## 2. MULTI-SERIES PLOTS WITH DUAL AXES

### 2.1 Problem

Current: 1 plot = 1 X, 1 Y per series
Needed: 1 plot = multiple series, optional secondary Y-axis

Example:
```
Plot "Sales vs Time"
├─ Series 1: Revenue (Y-axis left, $)
├─ Series 2: Units Sold (Y-axis right, count)
├─ Series 3: Profit Margin (Y-axis left, %)
```

### 2.2 Frontend - PlotBuilder.jsx Refactor

```jsx
const PlotBuilder = ({ sessionId }) => {
  const [plotConfig, setPlotConfig] = useState({
    title: '',
    x_axis: null,
    series: [
      {
        id: 'series_1',
        y_column: null,
        y_axis: 'left',  // 'left' | 'right'
        plot_type: 'scatter',  // scatter, line, bar, etc
        name: 'Series 1',
        color: '#1f77b4'
      }
    ]
  });
  
  const addSeries = () => {
    const newSeries = {
      id: `series_${Date.now()}`,
      y_column: null,
      y_axis: 'left',
      plot_type: 'scatter',
      name: `Series ${plotConfig.series.length + 1}`,
      color: generateColor()
    };
    setPlotConfig({
      ...plotConfig,
      series: [...plotConfig.series, newSeries]
    });
  };
  
  const removeSeries = (seriesId) => {
    setPlotConfig({
      ...plotConfig,
      series: plotConfig.series.filter(s => s.id !== seriesId)
    });
  };
  
  const updateSeries = (seriesId, updates) => {
    setPlotConfig({
      ...plotConfig,
      series: plotConfig.series.map(s =>
        s.id === seriesId ? { ...s, ...updates } : s
      )
    });
  };
  
  return (
    <div className="plot-builder">
      <div className="plot-config">
        {/* Title */}
        <input 
          placeholder="Plot title"
          value={plotConfig.title}
          onChange={(e) => setPlotConfig({...plotConfig, title: e.target.value})}
        />
        
        {/* X-Axis */}
        <select 
          value={plotConfig.x_axis || ''}
          onChange={(e) => setPlotConfig({...plotConfig, x_axis: e.target.value})}
        >
          <option value="">Select X-axis column</option>
          {columns.map(col => <option key={col} value={col}>{col}</option>)}
        </select>
        
        {/* Series List */}
        <div className="series-list">
          <h3>Series ({plotConfig.series.length})</h3>
          {plotConfig.series.map((series, idx) => (
            <SeriesEditor
              key={series.id}
              series={series}
              columns={columns}
              onUpdate={(updates) => updateSeries(series.id, updates)}
              onRemove={() => removeSeries(series.id)}
              hasSecondaryAxis={plotConfig.series.some(s => s.y_axis === 'right')}
            />
          ))}
          <button onClick={addSeries} className="btn-add-series">
            + Add Series
          </button>
        </div>
        
        {/* Dual Y-Axis Info */}
        {plotConfig.series.some(s => s.y_axis === 'right') && (
          <div className="info">
                ✓ Secondary Y-axis enabled
          </div>
        )}
      </div>
      
      {/* Preview */}
      <PlotPreviewMultiSeries 
        config={plotConfig}
        sessionId={sessionId}
      />
    </div>
  );
};

const SeriesEditor = ({ series, columns, onUpdate, onRemove, hasSecondaryAxis }) => {
  return (
    <div className="series-editor">
      <input 
        placeholder="Series name"
        value={series.name}
        onChange={(e) => onUpdate({ name: e.target.value })}
      />
      
      <select 
        value={series.y_column || ''}
        onChange={(e) => onUpdate({ y_column: e.target.value })}
      >
        <option value="">Select Y column</option>
        {columns.filter(c => isNumeric(c)).map(col => 
          <option key={col} value={col}>{col}</option>
        )}
      </select>
      
      <select 
        value={series.plot_type}
        onChange={(e) => onUpdate({ plot_type: e.target.value })}
      >
        <option value="scatter">Scatter</option>
        <option value="line">Line</option>
        <option value="bar">Bar</option>
        <option value="area">Area</option>
      </select>
      
      <select 
        value={series.y_axis}
        onChange={(e) => onUpdate({ y_axis: e.target.value })}
      >
        <option value="left">Left Y-axis</option>
        <option value="right" disabled={!hasSecondaryAxis && series.y_axis === 'left'}>
          Right Y-axis (secondary)
        </option>
      </select>
      
      <input 
        type="color"
        value={series.color}
        onChange={(e) => onUpdate({ color: e.target.value })}
        title="Series color"
      />
      
      <button onClick={onRemove} className="btn-remove">✕</button>
    </div>
  );
};
```

### 2.3 Backend - Multi-Series Plot Route

```python
@app.post("/api/plot/multi-series")
async def plot_multi_series(body: dict):
    """
    Create plot with multiple series and optional dual Y-axis
    
    Body:
    {
      "session_id": "...",
      "title": "Sales Analysis",
      "x_axis": "date",
      "series": [
        {"y_column": "revenue", "y_axis": "left", "plot_type": "line", "name": "Revenue"},
        {"y_column": "units", "y_axis": "right", "plot_type": "bar", "name": "Units"}
      ]
    }
    """
    df = get_session_data(body['session_id'])
    config = body
    
    fig = go.Figure()
    
    # Determine if secondary Y-axis needed
    has_secondary = any(s['y_axis'] == 'right' for s in config['series'])
    
    # Add each series
    for series in config['series']:
        y_axis_ref = 'y2' if series['y_axis'] == 'right' else 'y'
        
        if series['plot_type'] == 'line':
            trace = go.Scatter(
                x=df[config['x_axis']],
                y=df[series['y_column']],
                mode='lines',
                name=series['name'],
                yaxis=y_axis_ref
            )
        elif series['plot_type'] == 'scatter':
            trace = go.Scatter(
                x=df[config['x_axis']],
                y=df[series['y_column']],
                mode='markers',
                name=series['name'],
                yaxis=y_axis_ref
            )
        elif series['plot_type'] == 'bar':
            trace = go.Bar(
                x=df[config['x_axis']],
                y=df[series['y_column']],
                name=series['name'],
                yaxis=y_axis_ref
            )
        # ... more types
        
        fig.add_trace(trace)
    
    # Layout with dual axes if needed
    layout_update = {
        'title': config['title'],
        'xaxis': {'title': config['x_axis']},
        'yaxis': {'title': 'Left Y-Axis'},
    }
    
    if has_secondary:
        layout_update['yaxis2'] = {
            'title': 'Right Y-Axis',
            'overlaying': 'y',
            'side': 'right'
        }
    
    fig.update_layout(**layout_update)
    
    return {'plot_json': fig.to_json()}
```

---

## 3. MULTI-GRAPH DASHBOARD

### 3.1 Frontend - Multi-Graph Manager

```jsx
const MultiGraphDashboard = ({ sessionId }) => {
  const [graphs, setGraphs] = useState([
    { id: 'graph_1', config: null, title: 'Graph 1' }
  ]);
  const [layout, setLayout] = useState('grid');  // 'grid' | '1col' | '2col'
  
  const addGraph = () => {
    const newGraph = {
      id: `graph_${Date.now()}`,
      config: null,
      title: `Graph ${graphs.length + 1}`
    };
    setGraphs([...graphs, newGraph]);
  };
  
  const removeGraph = (graphId) => {
    setGraphs(graphs.filter(g => g.id !== graphId));
  };
  
  const updateGraphConfig = (graphId, config) => {
    setGraphs(graphs.map(g => 
      g.id === graphId ? { ...g, config } : g
    ));
  };
  
  const exportAllGraphs = async () => {
    // Export all graphs as PDF with multiple pages
    const pdfDoc = new PDFDocument();
    
    for (const graph of graphs) {
      if (graph.config) {
        const imageBuffer = await graphToImage(graph.config);
        pdfDoc.addPage().image(imageBuffer, 50, 50, { width: 500 });
        pdfDoc.text(graph.title, 50, 560);
      }
    }
    
    pdfDoc.pipe(fs.createWriteStream(`graphs_${Date.now()}.pdf`));
  };
  
  return (
    <div className="multi-graph-dashboard">
      <div className="toolbar">
        <select value={layout} onChange={(e) => setLayout(e.target.value)}>
          <option value="grid">Grid Layout</option>
          <option value="1col">1 Column</option>
          <option value="2col">2 Columns</option>
        </select>
        
        <button onClick={addGraph}>+ Add Graph</button>
        <button onClick={exportAllGraphs}>📊 Export All as PDF</button>
      </div>
      
      <div className={`graphs-container layout-${layout}`}>
        {graphs.map(graph => (
          <GraphCard
            key={graph.id}
            graph={graph}
            sessionId={sessionId}
            onConfigUpdate={(config) => updateGraphConfig(graph.id, config)}
            onRemove={() => removeGraph(graph.id)}
          />
        ))}
      </div>
    </div>
  );
};

const GraphCard = ({ graph, sessionId, onConfigUpdate, onRemove }) => {
  const [isEditing, setIsEditing] = useState(!graph.config);
  const [plotData, setPlotData] = useState(null);
  
  const handleSavePlot = async (config) => {
    onConfigUpdate(config);
    
    // Fetch plot from backend
    const res = await fetch('/api/plot/multi-series', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        ...config
      })
    });
    const { plot_json } = await res.json();
    setPlotData(JSON.parse(plot_json));
    setIsEditing(false);
  };
  
  return (
    <div className="graph-card">
      <div className="graph-header">
        <h3>{graph.title}</h3>
        <div className="graph-actions">
          <button onClick={() => setIsEditing(!isEditing)}>
            {isEditing ? '✕' : '✏️'}
          </button>
          <button onClick={onRemove}>🗑️</button>
        </div>
      </div>
      
      {isEditing ? (
        <PlotBuilder
          sessionId={sessionId}
          onSave={handleSavePlot}
          initialConfig={graph.config}
        />
      ) : (
        plotData && <PlotPreviewMultiSeries data={plotData} />
      )}
    </div>
  );
};
```

### 3.2 CSS - Responsive Grid Layout

```css
.graphs-container {
  display: grid;
  gap: 20px;
  padding: 20px;
}

.layout-grid {
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
}

.layout-1col {
  grid-template-columns: 1fr;
}

.layout-2col {
  grid-template-columns: repeat(2, 1fr);
}

@media (max-width: 768px) {
  .graphs-container {
    grid-template-columns: 1fr;
  }
}

.graph-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}
```

---

## 4. ADVANCED OPTIMIZATION PASS

### 4.1 Audit Checklist

**Backend (app/)**
- [ ] All CSV loading via Polars lazy (not pandas)
- [ ] Stats computed lazily (no full .collect() until needed)
- [ ] Filters are lazy chains (deferred execution)
- [ ] GroupBy uses Polars native (not pandas)
- [ ] Exports stream in chunks (no full RAM load)
- [ ] No unnecessary .to_pandas() conversions
- [ ] ML operations vectorized (batch processing, no loops)
- [ ] Queries parallelized (multi-threaded where possible)
- [ ] Memory profiling: identify remaining bottlenecks

**Frontend (src/)**
- [ ] Virtual scrolling on all large tables
- [ ] Debounced all inputs (300ms+)
- [ ] Lazy load plots (on-demand, not auto-compute)
- [ ] Pagination: 100 rows/page max
- [ ] React.memo on all heavy components
- [ ] useMemo for expensive computations
- [ ] useCallback for event handlers
- [ ] No re-renders on every state change
- [ ] Code splitting: lazy load routes

### 4.2 Profiling Tools

**Backend Profiling**

```python
# app/profiling.py
import cProfile
import pstats
import io
from functools import wraps

def profile_operation(func):
    """Decorator to profile function execution"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        
        result = await func(*args, **kwargs)
        
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(10)  # Top 10
        
        print(f"Profile {func.__name__}:")
        print(s.getvalue())
        
        return result
    return wrapper

# Usage
@app.post("/api/groupby")
@profile_operation
async def groupby_endpoint(body):
    # ... implementation
    pass
```

**Frontend Profiling (React DevTools)**
```
Chrome DevTools → Performance tab
- Record operations
- Identify slow renders
- Check component updates
```

### 4.3 Vectorization Examples

**Bad (loops)**
```python
# SLOW - Row-by-row
for i in range(len(df)):
    df['new_col'][i] = df['col_a'][i] * df['col_b'][i]
```

**Good (vectorized)**
```python
# FAST - Polars vectorized
df = df.with_column(
    (pl.col('col_a') * pl.col('col_b')).alias('new_col')
)
```

### 4.4 Memory Profiling

```python
# app/memory_monitor.py
import tracemalloc
from functools import wraps

def memory_tracker(func):
    """Track peak memory usage"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tracemalloc.start()
        
        result = await func(*args, **kwargs)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"{func.__name__}: {peak / 1024 / 1024:.1f} MB peak")
        
        return result
    return wrapper
```

### 4.5 Database Query Optimization

```python
# BEFORE: Multiple queries
stats_count = df.select(pl.col('*').count()).collect()
stats_mean = df.select(pl.col('*').mean()).collect()
stats_std = df.select(pl.col('*').std()).collect()
# 3 full passes!

# AFTER: Single pass
stats = df.select([
    pl.col('*').count().alias('count'),
    pl.col('*').mean().alias('mean'),
    pl.col('*').std().alias('std'),
]).collect()
# 1 pass!
```

### 4.6 Caching Aggressive

```python
from functools import lru_cache
from datetime import datetime, timedelta

class AggressiveCache:
    def __init__(self, ttl_seconds=60):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return value
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, datetime.now())

# Cache everything that's idempotent
cache = AggressiveCache(ttl_seconds=300)  # 5 min TTL

@app.get("/api/stats/{session_id}")
def get_stats(session_id: str):
    cache_key = f"stats_{session_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    stats = compute_expensive_stats(session_id)
    cache.set(cache_key, stats)
    return stats
```

---

## 5. TESTING PHASE 10

### 5.1 Compressed Format Tests

```python
# test_compressed_formats.py
def test_csv_gz():
    """Test .csv.gz loading"""
    df = data_service.load_file('test_data/large.csv.gz')
    assert len(df) == 500_000
    assert 'name' in df.columns

def test_parquet_zstd():
    """Test .parquet.zstd"""
    df = data_service.load_file('test_data/large.parquet.zstd')
    assert len(df) == 500_000

def test_feather():
    """Test .feather (Arrow IPC)"""
    df = data_service.load_file('test_data/large.feather')
    assert len(df) == 500_000
```

### 5.2 Multi-Series Plot Tests

```python
def test_multi_series_plot():
    """Test plot with 3 series"""
    config = {
        'title': 'Multi-Series',
        'x_axis': 'date',
        'series': [
            {'y_column': 'revenue', 'y_axis': 'left', 'plot_type': 'line'},
            {'y_column': 'units', 'y_axis': 'right', 'plot_type': 'bar'},
        ]
    }
    result = plot_multi_series(config)
    assert 'plot_json' in result
    assert 'yaxis2' in result['plot_json']  # Dual axis
```

### 5.3 Performance Regression Tests

```python
def test_groupby_performance():
    """Ensure groupby stays fast"""
    df = pl.scan_csv('test_data/large_500k.csv')
    start = time.time()
    result = df.groupby(['dept']).agg([pl.col('salary').mean()]).collect()
    duration = time.time() - start
    
    assert duration < 0.5, f"GroupBy too slow: {duration}s"

def test_stats_performance():
    """Ensure stats computation stays fast"""
    df = pl.scan_csv('test_data/large_1m.csv')
    start = time.time()
    stats = df.select([pl.col('*').mean()]).collect()
    duration = time.time() - start
    
    assert duration < 1.0, f"Stats too slow: {duration}s"
```

---

## 6. GIT WORKFLOW

```bash
# Create new branch
git checkout -b feature/phase-10-compression-multiplot-optimization

# Work in stages:
git commit -m "feat: add compressed format support (.gz, .bz2, .zip, .feather)"
git commit -m "feat: multi-series plots with dual Y-axis support"
git commit -m "feat: multi-graph dashboard with layout options"
git commit -m "refactor: optimization pass - vectorize operations, aggressive caching"
git commit -m "test: comprehensive tests for Phase 10 features"
git commit -m "docs: update PERFORMANCE.md with new benchmarks"

git push origin feature/phase-10-compression-multiplot-optimization

# Create PR and merge after CI passes
```

---

## 7. SUCCESS CRITERIA

✅ All compressed formats load without error  
✅ Multi-series plots render correctly  
✅ Dual Y-axis displays properly  
✅ Multi-graph dashboard responsive  
✅ 1GB+ file loads in < 10 seconds  
✅ GroupBy on 1M rows in < 1 second  
✅ No memory spike on export  
✅ All operations vectorized (no Python loops)  
✅ Frontend renders smoothly (< 16ms per frame)  
✅ Performance benchmarks improved 20%+ over Phase 9