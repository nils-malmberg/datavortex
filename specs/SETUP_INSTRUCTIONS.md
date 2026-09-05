# Guide de Configuration - DataVortex

## Initialisation projet

```bash
# Créer structure
mkdir datavortex && cd datavortex
git init

# Backend
mkdir backend && cd backend
uv init
# Ajouter dependencies via pyproject.toml

# Frontend
cd ..
# [npm create react-app frontend / ou npm create vite]

# Git
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin git@github.com:nils-malmberg/datavortex.git
git push -u origin main
```

## Dependencies Python

```toml
[project]
dependencies = [
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "pandas==2.1.0",
    "numpy==1.24.0",
    "scipy==1.11.0",
    "plotly==5.17.0",
    "python-multipart==0.0.6",
    "chardet==5.2.0",  # Détection encoding
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.0",
    "black==23.11.0",
]
```

## CI/CD GitHub Actions

À implémenter après structure de base.