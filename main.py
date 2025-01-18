from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import docker,general
from config.setting import CORS_CONFIG


app = FastAPI()

app.add_middleware(CORSMiddleware, **CORS_CONFIG)

app.include_router(general.router)
app.include_router(docker.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)