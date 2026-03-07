# run.ps1 - Script chay APP tren Windows (Backend + Frontend)
# Backend (Python) & Frontend (Node) chay tai day.
# DB & AI chay tren WSL.

param(
    [switch]$skip
)

Write-Host "Dang khoi dong Ung dung tren Windows..." -ForegroundColor Green

# Kiem tra Python (uu tien 'py' launcher roi den 'python')
$PYTHON_CMD = "python"
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PYTHON_CMD = "py"
    Write-Host "[INFO] Phat hien Python Launcher ('py'). Se su dung no."
} elseif (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Khong tim thay 'python' hoac 'py'. Vui long cai dat Python!" -ForegroundColor Red
    exit 1
}

# 1. Backend
Write-Host "Dang thiet lap Backend..." -ForegroundColor Green
Set-Location backend

# Tao/Kiem tra venv
if (-not $skip) {
    if (-not (Test-Path "venv")) {
        Write-Host "Dang tao venv..."
        & $PYTHON_CMD -m venv venv
    }
    
    # Kiem tra xem venv co tao thanh cong khong
    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Write-Host "[ERROR] Khong tim thay python trong venv. Co the venv bi loi." -ForegroundColor Red
        Write-Host "Hay xoa thu muc 'backend/venv' va chay lai script."
        exit 1
    }

    Write-Host "Dang cai dat thu vien..."
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
}

# Init DB
Write-Host "Dang ket noi DB (WSL)..."
.\venv\Scripts\python.exe -m app.db.init_db

# Chay Backend
Write-Host "Dang khoi dong Backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '.\venv\Scripts\activate'; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app"

# 2. Frontend
Set-Location ..\frontend
Write-Host "Dang thiet lap Frontend..." -ForegroundColor Green

if (-not $skip) {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Dang cai dat node_modules..."
        npm install
    }
}

Write-Host "Dang khoi dong Frontend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Set-Location ..
Write-Host "Da khoi chay xong!" -ForegroundColor Green
