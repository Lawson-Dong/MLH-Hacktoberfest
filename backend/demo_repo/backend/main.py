from fastapi import FastAPI

app = FastAPI()


@app.get("/api/projects")
def projects():
    return [{"id": "project_001", "name": "Campus Connect"}]


@app.get("/api/members")
def members():
    return [{"id": "member_001", "name": "Alex"}]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/tasks")
def tasks():
    return []
