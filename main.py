import uvicorn

def main():
    print("🌾 Starting Farm_com Autonomous Farm OS on http://localhost:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
