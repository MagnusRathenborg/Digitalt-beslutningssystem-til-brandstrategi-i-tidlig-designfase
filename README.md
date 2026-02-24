# Digitalt beslutningssystem til brandstrategi i tidlig designfase

Systemet omsætter brandkrav til et logisk værktøj, der (på baggrund af brugerinput) bestemmer anvendelseskategori, risikoklasse og brandklasse, samt viser relevante krav og understøtter dokumentation.

## Projektstruktur (kort)

- `backend/`
  - `server.py` – FastAPI-server (API + serving af frontend-filer)
  - `logic.py` – beslutningslogik/evaluering baseret på JSON-modeller
  - `br18_data.py` – korte beskrivelser/mapping (fx anvendelseskategorier)
- `frontend/`
  - `br18_full.html` – UI (wizard)
  - `style.css`, `theme.css` – styling
  - `assets/` – figurer/tabeller m.m. til bilag
  - `br18_knowledge/` – videns-/regeldata (JSON)
  - `validation/validation.json` – valideringsdata til UI
  - `requirements.json` – UI-regel/kravsæt (fx for bilag)
- JSON-filer i roden (bruges af backend og UI)
  - `Brandklasse_Bestemmelse.json` – beslutningsmodel for brandklasse-flow
  - `Krav.json` – kravmodel
  - `input1.json`, `inputB1.json`, `inputB11.json` – eksempel-input/templates

## Forudsætninger

- Git (til at clone repoet)
- Python 3.10+ (anbefalet)
- (Valgfrit) VS Code + Python extension

## Kom i gang (Windows / PowerShell)

Kør fra projektets rodmappe:

```powershell
# 1) Opret virtuel environment
python -m venv .venv

# 2) Aktivér
.\.venv\Scripts\Activate.ps1

# Hvis aktivering bliver blokeret af Execution Policy, kan du midlertidigt tillade det i den aktuelle terminal:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3) Installer dependencies
pip install fastapi "uvicorn[standard]"

# 4) Start backend (kør fra backend-mappen)
Set-Location .\backend
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000

# Alternativ (uden at aktivere venv):
# Set-Location .\backend
# ..\.venv\Scripts\python.exe -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Åbn derefter i browser:

- UI (manual/wizard): `http://127.0.0.1:8000/manual`
- Kør br18_full.html via. Live Server

## Noter

- Frontend forventer som udgangspunkt backend på `http://127.0.0.1:8000` (se `API_BASE` i `frontend/br18_full.html`).
- Backend server både API-endpoints (fx `/evaluate-complete`, `/evaluate-krav`) og de statiske frontend-filer (`/manual`, `/style.css`, `/assets/...`).
