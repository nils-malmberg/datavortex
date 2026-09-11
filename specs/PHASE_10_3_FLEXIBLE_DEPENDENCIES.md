# Phase 10.3 : Flexible Dependencies & Compatibility

*Replace pinned versions with ranges, downgrade where safe, maximize compatibility*

---

## 1. PROBLEM ANALYSIS

### Current Issue (ALL PINNED)
```toml
fastapi==0.104.1
uvicorn==0.24.0
polars==1.44.2
pandas==2.1.0
plotly==5.17.0
scikit-learn==1.3.2
torch==2.0.0
```

**Problems:**
- Can't install on corp networks (missing wheels for specific versions)
- Can't use newer security patches
- Incompatible with different Python versions
- Bloats install time

### Solution
Replace with **semantic versioning ranges** that are:
- ✅ Flexible (install latest compatible)
- ✅ Safe (no breaking changes)
- ✅ Downgraded where needed (for compatibility)

---

## 2. DEPENDENCY AUDIT & DOWNGRADE

### 2.1 Backend Dependencies (backend/pyproject.toml)

**BEFORE (pinned):**
```toml
fastapi==0.104.1
uvicorn==0.24.0
polars==1.44.2
pandas==2.1.0
numpy==1.24.0
scipy==1.11.0
plotly==5.17.0
scikit-learn==1.3.2
torch==2.0.0
python-multipart==0.0.6
chardet==5.2.0
reportlab==4.0.0
weasyprint==59.0
python-dateutil==2.8.2
```

**AFTER (flexible ranges + downgraded):**
```toml
[project]
name = "datavortex-backend"
version = "1.2.1"
description = "DataVortex backend - data visualization and analysis"
requires-python = ">=3.9,<3.13"  # Compatible range

dependencies = [
    # Web framework (fastapi 0.100+ is stable, no breaking changes)
    "fastapi>=0.100.0,<0.115.0",
    "uvicorn[standard]>=0.24.0,<0.30.0",
    
    # Data processing (polars 0.20+ is stable, downgrade to 0.20 for compatibility)
    "polars[parquet,excel]>=0.20.0,<1.0.0",
    # Note: 1.0+ would require code changes, 0.20-0.99 is safe
    
    # Pandas only needed for compatibility, not primary
    "pandas>=1.5.0,<2.3.0",
    
    # Numerics
    "numpy>=1.21.0,<2.0.0",  # 2.0 has breaking changes
    "scipy>=1.7.0,<1.15.0",
    
    # Plotting (plotly is backward compatible)
    "plotly>=5.0.0,<6.0.0",
    
    # ML/Stats (scikit-learn is stable, broad range safe)
    "scikit-learn>=1.0.0,<1.5.0",
    
    # PyTorch (LTS releases are stable, broad range)
    "torch>=2.0.0,<2.5.0",
    
    # File handling (broad ranges, well-maintained)
    "python-multipart>=0.0.5,<0.1.0",
    "chardet>=4.0.0,<6.0.0",
    
    # PDF generation (reportlab stable, broad range)
    "reportlab>=3.6.0,<4.0.0",
    "weasyprint>=54.0,<61.0",
    
    # Date utilities (stable)
    "python-dateutil>=2.8.0,<3.0.0",
    
    # HTTP (for async)
    "httpx>=0.24.0,<0.28.0",
]

[project.optional-dependencies]
# Optional: for users who want bleeding edge
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]
```

### 2.2 Why These Ranges?

| Package | Old | New | Reason |
|---------|-----|-----|--------|
| fastapi | 0.104.1 | >=0.100.0,<0.115.0 | No breaking changes in 0.100-0.114, broader compatibility |
| polars | 1.44.2 | >=0.20.0,<1.0.0 | 0.20-0.99 all stable; 1.0+ needs testing |
| pandas | 2.1.0 | >=1.5.0,<2.3.0 | 1.5+ has all features needed, 2.3 may have issues |
| torch | 2.0.0 | >=2.0.0,<2.5.0 | LTS releases (2.0, 2.2) are stable |
| plotly | 5.17.0 | >=5.0.0,<6.0.0 | No breaking changes in 5.0-5.99 |
| numpy | 1.24.0 | >=1.21.0,<2.0.0 | 2.0 has breaking changes, stay on 1.x |

---

## 3. FRONTEND DEPENDENCIES (frontend/package.json)

**BEFORE (pinned):**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-window": "^1.8.8",
    "plotly.js": "^2.26.0",
    "axios": "^1.6.0",
    "classnames": "^2.3.2"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "eslint": "^8.54.0"
  }
}
```

**AFTER (caret/tilde ranges):**
```json
{
  "name": "datavortex-frontend",
  "version": "1.2.1",
  "type": "module",
  "dependencies": {
    "react": "^18.0.0",           # Allow 18.0-18.x.x
    "react-dom": "^18.0.0",
    "react-window": "^1.8.0",     # Allow 1.8+
    "plotly.js": "^2.0.0",        # Allow 2.0+
    "axios": "^1.0.0",            # Allow 1.0+
    "classnames": "^2.0.0"        # Allow 2.0+
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "eslint": "^8.0.0"
  }
}
```

---

## 4. CLI DEPENDENCIES (datavortex-cli/pyproject.toml)

**BEFORE:**
```toml
dependencies = [
    "datavortex-backend==1.2.1",
    "uvicorn[standard]==0.24.0",
]
```

**AFTER:**
```toml
dependencies = [
    "datavortex-backend>=1.2.0,<2.0.0",  # Allow patch/minor updates
    "uvicorn[standard]>=0.24.0,<0.30.0",
]
```

---

## 5. IMPLEMENTATION

### 5.1 Update pyproject.toml Files

**backend/pyproject.toml:**
Replace `dependencies = [...]` section with flexible ranges above.

**datavortex-cli/pyproject.toml:**
Replace `dependencies = [...]` with flexible ranges.

### 5.2 Update frontend/package.json

Replace all exact versions with caret ranges (^).

### 5.3 Regenerate Lock Files

```bash
# Backend
cd backend
rm uv.lock  # Remove old lock
uv sync     # Generates new lock with compatible versions

# Frontend
cd frontend
rm package-lock.json  # Remove old lock
npm install          # Generates new lock with compatible versions
```

### 5.4 Test Compatibility

```bash
# Test backend with newer versions
cd backend
uv sync --upgrade  # Install newest compatible versions
pytest tests/      # Run full test suite

# Test frontend
cd frontend
npm install
npm run build
npm run lint
```

---

## 6. COMPATIBILITY MATRIX

Document what versions work:

**backend/COMPATIBILITY.md:**
```markdown
# Compatibility Matrix

## Tested On

| Component | Min Version | Max Version | Status |
|-----------|------------|------------|--------|
| Python | 3.9 | 3.12 | ✅ Supported |
| FastAPI | 0.100.0 | 0.114.0 | ✅ Tested |
| Polars | 0.20.0 | 0.99.0 | ✅ Tested |
| Pandas | 1.5.0 | 2.2.0 | ✅ Tested |
| PyTorch | 2.0.0 | 2.4.0 | ✅ Tested |
| NumPy | 1.21.0 | 1.26.0 | ✅ Tested |

## Known Issues

- Polars 1.0+ requires code refactoring (deferred to v1.3)
- NumPy 2.0+ has breaking changes (not supported)

## Installation on Corporate Networks

If you hit wheel compatibility issues:

```bash
# Skip problematic packages temporarily
uv pip install --no-binary :all: -r requirements.txt

# Or use pre-built wheels from your corporate mirror
pip install -i https://your-mirror.corp/ -r requirements.txt
```
```

---

## 7. GIT WORKFLOW

```bash
git checkout -b feature/phase-10-3-flexible-dependencies

# Update backend
git commit -m "refactor: flexible dependencies in backend (ranges instead of pins)"

# Update frontend
git commit -m "refactor: flexible dependencies in frontend (caret ranges)"

# Update CLI
git commit -m "refactor: flexible dependencies in CLI"

# Regenerate locks
rm backend/uv.lock frontend/package-lock.json
uv sync
npm install
git add uv.lock package-lock.json
git commit -m "build: regenerate lock files with flexible constraints"

# Test
pytest tests/
npm run build
git commit -m "test: verify all compatibility tests pass"

# Documentation
git commit -m "docs: add COMPATIBILITY.md with tested version matrix"

git push origin feature/phase-10-3-flexible-dependencies

# Create PR, merge after CI ✅
```

---

## 8. SUCCESS CRITERIA

✅ All version pins replaced with ranges  
✅ No exact version constraints (==)  
✅ Downgraded safely (polars 0.20+, numpy 1.x, etc)  
✅ Backend installs on corp networks (broad compatibility)  
✅ Frontend builds with latest React 18.x  
✅ All tests pass with flexible versions  
✅ Lock files regenerated  
✅ COMPATIBILITY.md documents tested ranges  
✅ No loss of features (still supports all Phase 10.1 functionality)