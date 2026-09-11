# Phase 10.2 : Fix Build, Version Consistency, Separator Regex

*Rebuild frontend, fix version numbers, add regex separator support*

---

## 1. BUILD PIPELINE FIX

### 1.1 Problem
- Frontend never compiled before push
- `datavortex-cli/datavortex/static/` contains old/missing files
- Users get outdated UI when installing via `uv tool install`

### 1.2 Solution: Build Before Push

**Create build script** (root level):

```bash
# build.sh (macOS/Linux)
#!/bin/bash
set -e

echo "🔨 Building DataVortex..."

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Copy static files to CLI
rm -rf datavortex-cli/datavortex/static
cp -r frontend/dist datavortex-cli/datavortex/static

echo "✅ Build complete"
echo "📦 Ready to commit and push"
```

```powershell
# build.ps1 (Windows)
$ErrorActionPreference = "Stop"

Write-Host "🔨 Building DataVortex..."

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Copy static files to CLI
Remove-Item -Recurse -Force datavortex-cli/datavortex/static -ErrorAction SilentlyContinue
Copy-Item -Recurse frontend/dist datavortex-cli/datavortex/static

Write-Host "✅ Build complete"
Write-Host "📦 Ready to commit and push"
```

**Usage before every release:**
```bash
# macOS/Linux
./build.sh

# Windows
.\build.ps1

# Then:
git add .
git commit -m "build: rebuild frontend for v1.2.X"
git push
```

### 1.3 Update package.json (root & frontend)

**Root package.json** (if doesn't exist, create):
```json
{
  "name": "datavortex",
  "version": "1.2.1",
  "private": true,
  "scripts": {
    "build": "cd frontend && npm install && npm run build && cd .. && rm -rf datavortex-cli/datavortex/static && cp -r frontend/dist datavortex-cli/datavortex/static",
    "dev": "concurrently \"cd backend && uv run uvicorn app.main:app --reload\" \"cd frontend && npm run dev\"",
    "test": "cd backend && uv run pytest"
  }
}
```

**frontend/package.json** - ensure version matches:
```json
{
  "name": "datavortex-frontend",
  "version": "1.2.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": { ... }
}
```

---

## 2. VERSION CONSISTENCY

### 2.1 Single Source of Truth

All version references MUST point to one place.

**backend/pyproject.toml:**
```toml
[project]
name = "datavortex-backend"
version = "1.2.1"  # ← SINGLE SOURCE
description = "..."
```

**frontend/package.json:**
```json
{
  "name": "datavortex-frontend",
  "version": "1.2.1",  # ← MUST MATCH
  ...
}
```

**datavortex-cli/pyproject.toml:**
```toml
[project]
name = "datavortex"
version = "1.2.1"  # ← MUST MATCH
dependencies = [
    "datavortex-backend==1.2.1",  # ← LOCKED VERSION
]
```

**README.md:**
```markdown
# DataVortex v1.2.1
```

**CHANGELOG.md:**
```markdown
## [1.2.1] - YYYY-MM-DD
```

**backend/app/main.py:**
```python
__version__ = "1.2.1"

@app.get("/api/version")
def get_version():
    return {"version": __version__}
```

### 2.2 Version Sync Script

Create `scripts/sync-versions.py`:

```python
#!/usr/bin/env python3
"""Sync all version numbers to single value"""
import re
import sys

TARGET_VERSION = "1.2.1"

files = {
    "backend/pyproject.toml": r'version = "([0-9.]+)"',
    "frontend/package.json": r'"version": "([0-9.]+)"',
    "datavortex-cli/pyproject.toml": r'version = "([0-9.]+)"',
    "README.md": r'# DataVortex v([0-9.]+)',
}

for filepath, pattern in files.items():
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        new_content = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), TARGET_VERSION), content)
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        
        print(f"✅ {filepath} → {TARGET_VERSION}")
    except FileNotFoundError:
        print(f"⚠️  {filepath} not found")

print(f"\n✅ All versions synced to {TARGET_VERSION}")
```

**Run before every release:**
```bash
python scripts/sync-versions.py
git add .
git commit -m "chore: sync versions to v1.2.1"
```

---

## 3. SEPARATOR REGEX SUPPORT

### 3.1 Problem
Currently: separators are fixed (`,`, `;`, `\t`)
Needed: allow custom regex (e.g., `\s+` for multiple spaces, `[,;]` for multiple delimiters)

### 3.2 Frontend - Separator Selector

**Upload.jsx - add regex option:**

```jsx
const Upload = () => {
  const [separatorType, setSeparatorType] = useState('auto');  // 'auto' | 'preset' | 'regex'
  const [separator, setSeparator] = useState(',');
  const [regexPattern, setRegexPattern] = useState('');
  
  const handleSeparatorChange = (type) => {
    setSeparatorType(type);
    if (type === 'preset') {
      setSeparator(',');
    } else if (type === 'regex') {
      setRegexPattern('\\s+');  // Default: one or more whitespace
    }
  };
  
  return (
    <div className="upload-panel">
      <h3>Separator Options</h3>
      
      {/* Type selector */}
      <div className="separator-types">
        <label>
          <input type="radio" value="auto" checked={separatorType === 'auto'} onChange={() => handleSeparatorChange('auto')} />
          🤖 Auto-detect
        </label>
        
        <label>
          <input type="radio" value="preset" checked={separatorType === 'preset'} onChange={() => handleSeparatorChange('preset')} />
          📋 Preset
        </label>
        
        <label>
          <input type="radio" value="regex" checked={separatorType === 'regex'} onChange={() => handleSeparatorChange('regex')} />
          🔧 Regex (Advanced)
        </label>
      </div>
      
      {/* Preset selector */}
      {separatorType === 'preset' && (
        <select value={separator} onChange={(e) => setSeparator(e.target.value)}>
          <option value=",">Comma (,)</option>
          <option value=";">Semicolon (;)</option>
          <option value="\t">Tab (\t)</option>
          <option value="|">Pipe (|)</option>
          <option value=" ">Space</option>
        </select>
      )}
      
      {/* Regex input */}
      {separatorType === 'regex' && (
        <div className="regex-input">
          <input 
            type="text"
            placeholder="Enter regex pattern (e.g., \s+, [,;], \s*,\s*)"
            value={regexPattern}
            onChange={(e) => setRegexPattern(e.target.value)}
          />
          <small>Examples: <code>\s+</code> (spaces), <code>[,;]</code> (comma or semicolon), <code>\s*,\s*</code> (comma with spaces)</small>
          
          {/* Validate regex */}
          {regexPattern && (
            <div className="regex-validation">
              {isValidRegex(regexPattern) ? (
                <span className="valid">✓ Valid regex</span>
              ) : (
                <span className="invalid">✗ Invalid regex</span>
              )}
            </div>
          )}
        </div>
      )}
      
      <button onClick={handleUpload} disabled={separatorType === 'regex' && !isValidRegex(regexPattern)}>
        📤 Upload
      </button>
    </div>
  );
};

function isValidRegex(pattern) {
  try {
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
}
```

### 3.3 Backend - Regex Parsing

**app/data_service.py:**

```python
import polars as pl
import re

class DataService:
    def load_csv_with_separator(self, file_path: str, sep_type: str, sep_value: str = None) -> pl.DataFrame:
        """
        Load CSV with various separator types
        
        sep_type: 'auto' | 'preset' | 'regex'
        sep_value: separator string or regex pattern
        """
        
        if sep_type == 'auto':
            # Polars auto-detect
            return pl.read_csv(file_path)
        
        elif sep_type == 'preset':
            # Fixed separator
            # Handle escape sequences
            sep_map = {
                '\\t': '\t',
                '\\n': '\n',
            }
            actual_sep = sep_map.get(sep_value, sep_value)
            return pl.read_csv(file_path, separator=actual_sep)
        
        elif sep_type == 'regex':
            # Regex separator - need manual parsing
            return self._load_csv_regex(file_path, sep_value)
        
        else:
            raise ValueError(f"Unknown separator type: {sep_type}")
    
    def _load_csv_regex(self, file_path: str, pattern: str) -> pl.DataFrame:
        """Parse CSV with regex separator"""
        try:
            # Validate regex
            regex = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}")
        
        # Read file and split by regex
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse header
        header = regex.split(lines[0].strip())
        
        # Parse data rows
        data = []
        for line in lines[1:]:
            if line.strip():
                values = regex.split(line.strip())
                data.append(values)
        
        # Create DataFrame
        df = pl.DataFrame(
            {col: [row[i] if i < len(row) else None for row in data] for i, col in enumerate(header)}
        )
        
        return df
```

### 3.4 Upload Route

**app/main.py:**

```python
@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    sep_type: str = Form("auto"),
    sep_value: str = Form(None)
):
    """
    Upload CSV with custom separator
    
    Query params:
    - sep_type: 'auto' | 'preset' | 'regex'
    - sep_value: separator or regex pattern
    """
    
    file_path = save_uploaded_file(file)
    
    try:
        # Load with specified separator
        df = data_service.load_csv_with_separator(file_path, sep_type, sep_value)
        
        session_id = generate_session_id()
        session_store[session_id] = {
            'file_path': file_path,
            'dataframe': df,
            'separator': {'type': sep_type, 'value': sep_value},
            'created_at': datetime.now()
        }
        
        return {
            'session_id': session_id,
            'rows': len(df),
            'columns': df.columns,
            'separator_used': {'type': sep_type, 'value': sep_value}
        }
    
    except Exception as e:
        return {'error': str(e)}, 400
```

---

## 4. GIT WORKFLOW

```bash
# Create branch
git checkout -b feature/phase-10-2-build-versions-regex

# 1. Build script + version sync
git commit -m "build: add build.sh/.ps1 and sync-versions.py"

# 2. Fix version numbers everywhere
python scripts/sync-versions.py
git commit -m "chore: sync all versions to v1.2.1"

# 3. Rebuild frontend
./build.sh  # or .\build.ps1 on Windows
git commit -m "build: rebuild frontend for v1.2.1"

# 4. Separator regex
git commit -m "feat: regex support for CSV separators"

# 5. Test & verify
pytest tests/
git commit -m "test: add tests for regex separators"

git push origin feature/phase-10-2-build-versions-regex

# Create PR, merge after CI ✅

git checkout main
git pull
git merge feature/phase-10-2-build-versions-regex
git push origin main

# Tag v1.2.1 (or v1.2.2 if already tagged)
git tag -a v1.2.1 -m "DataVortex v1.2.1 - Build fixes, version consistency, regex separators"
git push origin v1.2.1
```

---

## 5. SUCCESS CRITERIA

✅ Build script compiles frontend before push  
✅ All version numbers consistent (backend, frontend, CLI, docs)  
✅ Version sync script works  
✅ Regex separator parsing works (e.g., `\s+`, `[,;]`)  
✅ Regex validation on frontend (no invalid patterns submitted)  
✅ Frontend properly compiled in `static/` folder  
✅ `uv tool install` gets current code with UI features  
✅ All tests pass (including separator tests)