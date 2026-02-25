import os
import sys
import psycopg2
import requests
from dotenv import load_dotenv

# Load env variables
load_dotenv()

POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123!@#")
POSTGRES_DB = os.getenv("POSTGRES_DB", "unimind")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = os.getenv("QDRANT_PORT", 6333)
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

# Note: The codebase uses http://localhost:8080/v1 for llama.cpp compatible server
AI_SERVER_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:8080/v1") 

def check_postgres():
    print(f"Checking PostgreSQL ({POSTGRES_SERVER})...", end=" ")
    try:
        conn = psycopg2.connect(
            host=POSTGRES_SERVER,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB
        )
        conn.close()
        print("✅ OK")
        return True
    except Exception as e:
        print("❌ FAILED")
        print(f"  Error: {e}")
        return False

def check_qdrant():
    print(f"Checking Qdrant ({QDRANT_URL})...", end=" ")
    try:
        # Check Qdrant health/collections
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        if resp.status_code == 200:
            print("✅ OK")
            return True
        else:
            print(f"❌ FAILED (Status: {resp.status_code})")
            return False
    except Exception as e:
        print("❌ FAILED")
        print(f"  Error: {e}")
        return False

def check_ai_server():
    # llama.cpp server usually has /health or just responds to /v1/models
    check_url = AI_SERVER_URL.replace("/v1", "/health") 
    print(f"Checking AI Server ({AI_SERVER_URL})...", end=" ")
    try:
        # Try health endpoint first
        resp = requests.get(check_url, timeout=5)
        if resp.status_code == 200:
             print("✅ OK (Health Check)")
             return True
        
        # Fallback to models endpoint if health endpoint differs
        models_url = f"{AI_SERVER_URL}/models"
        resp = requests.get(models_url, timeout=5)
        if resp.status_code == 200:
            print("✅ OK (Models Endpoint)")
            return True
        else:
            print(f"❌ FAILED (Status: {resp.status_code})")
            return False
    except Exception as e:
        print("❌ FAILED")
        print(f"  Error: {e}")
        return False

if __name__ == "__main__":
    print("--- SYSTEM HEALTH CHECK ---")
    pg_ok = check_postgres()
    qdrant_ok = check_qdrant()
    ai_ok = check_ai_server()
    print("---------------------------")
    
    if pg_ok and qdrant_ok and ai_ok:
        print("🎉 ALL SYSTEMS GO! Backend is connected to WSL services.")
        sys.exit(0)
    else:
        print("⚠️ SOME SYSTEMS FAILED. Please check services in WSL.")
        sys.exit(1)
