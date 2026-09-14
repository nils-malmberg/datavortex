# Phase 10.4 : Fix Subplot Grid Layout & TensorFlow Import Issues

*Fix UI scrolling, investigate ML errors, ensure consistent behavior across environments*

---

## 1. SUBPLOT GRID LAYOUT BUG

### 1.1 Problem
When user selects 3+ rows or 2+ columns in subplot grid:
- Plot area doesn't expand vertically/horizontally
- Subplots shrink and overlap
- Bad readability, can't see plots properly
- No scrollbar appears

### 1.2 Root Cause
CSS likely has fixed height/width on plot container. Need flexible sizing.

### 1.3 Solution

**frontend/src/components/Visualization.jsx or PlotBuilder.jsx**

Find the subplot grid container and fix CSS:

```jsx
// BEFORE (BAD - fixed size)
const PlotPreviewGrid = ({ config }) => {
  return (
    <div style={{ height: '600px', width: '100%' }}>
      {/* Subplots here - forces shrinking */}
    </div>
  );
};

// AFTER (GOOD - flexible size)
const PlotPreviewGrid = ({ config }) => {
  const { rows, cols } = config.subplot_grid;
  
  // Calculate height dynamically: 600px per row
  const containerHeight = rows * 600; // 600px = ideal subplot height
  
  return (
    <div style={{
      height: `${containerHeight}px`,
      width: '100%',
      overflowY: 'auto',  // ← Vertical scrollbar
      overflowX: 'auto',  // ← Horizontal scrollbar if needed
      border: '1px solid #ddd',
      borderRadius: '4px',
      padding: '10px'
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: '20px',
        width: '100%',
        height: 'fit-content'  // ← Don't force shrinking
      }}>
        {config.subplots.map((subplot, idx) => (
          <div key={subplot.id} style={{ minHeight: '500px' }}>
            {/* Individual plot */}
          </div>
        ))}
      </div>
    </div>
  );
};
```

**CSS in Visualization.css or inline styles:**

```css
.plot-container {
  /* REMOVE if exists:
  height: 600px;
  max-height: 600px;
  */
  
  /* ADD: */
  min-height: 600px;  /* Minimum, can grow */
  overflow-y: auto;   /* Vertical scroll */
  overflow-x: auto;   /* Horizontal scroll if needed */
}

.subplot-grid {
  display: grid;
  gap: 20px;
  padding: 10px;
  width: 100%;
  /* REMOVE if exists:
  height: 100%;
  */
  
  /* ADD: */
  height: fit-content;  /* Expand with content */
  grid-auto-rows: minmax(500px, auto);  /* Min 500px per row, can grow */
}

.subplot-item {
  /* REMOVE if exists:
  flex: 1;
  max-height: 300px;
  */
  
  /* ADD: */
  min-height: 500px;
  height: auto;  /* Don't force shrinking */
  overflow: hidden;  /* Keep plot contained */
}
```

**Test Cases:**
- 1x1 grid: displays full-size plot ✅
- 2x2 grid: displays 4 plots in 2x2, can scroll ✅
- 3x2 grid: displays 6 plots, vertical scroll appears ✅
- 4x3 grid: displays 12 plots, scrolls both directions ✅
- Each subplot stays large (500px+), no shrinking ✅

---

## 2. TENSORFLOW IMPORT ISSUE

### 2.1 Problem
**On Windows 11 (corporate environment):**
- ML operations fail with: `tensorflow.python import ...` error
- Other machines don't have this issue

**Likely Cause:**
- Corporate proxy/firewall blocking tensorflow wheels
- OR: tensorflow-io dependency missing on corporate machine
- OR: Polars/PyTorch using tensorflow internally somewhere (unlikely but check)

### 2.2 Investigation Steps

**Step 1: Identify the exact error**

When running ML operation, capture full traceback:
```python
# In backend/app/ml_service.py, wrap ML operations:
try:
    result = perform_ml_operation(data, config)
except ImportError as e:
    print(f"FULL ERROR: {e}")
    import traceback
    traceback.print_exc()
    return {'error': str(e), 'traceback': traceback.format_exc()}
```

**Step 2: Check dependencies**

```bash
# Backend
cd backend

# List all installed packages
uv pip list | grep -i tensor
uv pip list | grep -i torch
uv pip list | grep -i polars

# Check if tensorflow is installed (shouldn't be with flexible deps)
python -c "import tensorflow" 2>&1 || echo "TensorFlow not found (good!)"

# Check PyTorch
python -c "import torch; print(torch.__version__)"

# Check if any package imports tensorflow as side effect
python -c "import polars; import torch; print('OK')"
```

**Step 3: Audit code for tensorflow imports**

```bash
# Search for tensorflow imports
grep -r "tensorflow" backend/app/
grep -r "import tf" backend/app/

# Should find NOTHING if using PyTorch only
```

### 2.3 Solution

**If tensorflow is still in dependencies (shouldn't be):**

Remove from `backend/pyproject.toml`:
```toml
# REMOVE:
# tensorflow-cpu>=...
# tensorflow-io>=...
```

Rebuild:
```bash
cd backend
uv sync --refresh  # Force reinstall
```

**If an indirect dependency imports tensorflow:**

Find which package:
```bash
python -c "
import sys
import importlib
packages = ['polars', 'pandas', 'scikit-learn', 'plotly', 'torch']
for pkg in packages:
    try:
        mod = importlib.import_module(pkg)
        if hasattr(mod, '__file__'):
            print(f'{pkg}: OK')
    except ImportError as e:
        print(f'{pkg}: FAIL - {e}')
"
```

**If corporate proxy issue:**

Add proxy configuration:
```bash
# frontend and backend both
pip config set global.index-url https://your-corporate-mirror/pypi/simple/

# Or for this install only:
uv pip install --index-url https://your-corporate-mirror/pypi/simple/ ...
```

**Fallback: Remove ML features on corporate machine**

If all else fails, disable ML on this environment:
```python
# backend/app/main.py
USE_ML = False  # Set to True only on personal machine

@app.post("/api/ml/train")
async def train_model(body: dict):
    if not USE_ML:
        return {'error': 'ML features not available in this environment'}
    
    # ... ML code
```

### 2.4 Corporate Environment Checklist

Create `CORPORATE_SETUP.md`:

```markdown
# Corporate Network Setup

## If ML features fail:

1. Check proxy:
```bash
pip config list
```

2. Configure pip for corporate mirror:
```bash
pip config set global.index-url https://your-mirror/pypi/simple/
```

3. Disable ML (optional):
```bash
# Set environment variable
set DATAVORTEX_NO_ML=1  # Windows
export DATAVORTEX_NO_ML=1  # Linux/macOS
```

4. Or use offline wheels:
```bash
pip install --no-index --find-links=/path/to/wheels/ datavortex
```

## Verified Environments

- ✅ Personal Windows 11: Full ML support
- ✅ Corporate Windows 11: [Pending verification]
- ✅ macOS: Full support
- ✅ Linux: Full support
```

---

## 3. GIT WORKFLOW - CRITICAL POINTS

```bash
# ⚠️ IMPORTANT: Build BEFORE committing!

# 1. Fix subplot grid CSS/JSX
# frontend/src/components/Visualization.jsx
# (adjust heights, add overflow, remove max-height)

# 2. Fix TensorFlow import
# backend/app/ml_service.py
# (add error handling, check imports, update deps)

# 3. Test everything locally first
cd backend
uv sync
pytest tests/ -v
python -m uvicorn app.main:app --reload --port 8000 &

cd frontend
npm install
npm run build
npm run lint
npm run dev

# Verify in browser:
# - Subplots grid 3x2 → scrolls properly ✅
# - ML features work (no tensorflow errors) ✅

# 4. Only then commit
git add .
git commit -m "fix: subplot grid layout scrolling (dynamic height)
fix: tensorflow import issue (corporate environment)
test: added error handling for ML failures"

# 5. BEFORE push: rebuild
./build.sh  # or .\build.ps1 on Windows
# (ensures static files are updated)

git add datavortex-cli/datavortex/static/
git commit -m "build: rebuild frontend with layout and ML fixes"

# 6. Push and create PR
git push origin feature/phase-10-4-fixes
gh pr create --title "Phase 10.4: Fix Grid Layout & ML Errors" \
             --body "See specs/PHASE_10_4_FIXES.md"

# 7. After CI ✅ merge
gh pr merge <PR_NUMBER> --merge
```

---

## 4. SUCCESS CRITERIA

✅ Subplot grid 3+ rows: expands vertically, vertical scrollbar appears  
✅ Subplot grid 2+ cols: expands horizontally, horizontal scrollbar appears  
✅ Each subplot stays large (500px+), never shrinks  
✅ ML operations work on personal Windows 11  
✅ ML operations work on corporate Windows 11 (or graceful fallback)  
✅ No tensorflow.python import errors  
✅ Error handling shows meaningful messages  
✅ Frontend compiles without errors  
✅ All 501+ tests pass  
✅ CORPORATE_SETUP.md documents workarounds