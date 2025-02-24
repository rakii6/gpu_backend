from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import docker,general
from config.setting import CORS_CONFIG
from services.gpu_manager import GPUManager
from services.redis import RedisManager
from services.firebase_service import FirebaseService
from services.docker_service import DockerService
from security.rate_limiter import RateLimiter
from services.session_manager import SessionManager

redis_manager = RedisManager() #only one universal redis client connection is created
firebase_service = FirebaseService() #only onefirebase client is created.
docker_service = None
gpu_manager = None
session_manager = None

@asynccontextmanager
async def lifespan(app:FastAPI):
    global docker_service, gpu_manager, session_manager

    #Core initialization of Services

    gpu_manager= GPUManager(redis_manager) #gpumanager consumes this redis client for his own purpose
    print("GPU Manager initialized")

    session_manager = SessionManager(redis_manager, firebase_service, gpu_manager, None)
    print("Session Manager initialized")


    docker_service= DockerService(gpu_manager,firebase_service, redis_manager, None) #docker manager consumes gpu manger for his own purpose
    print("Docker Service initialized")

    print("Before linking:")
    print(f"DockerService session: {docker_service._session}")
    print(f"SessionManager docker: {session_manager._docker}")

    #here again we pass dockeer service, after it has been inistialized
    docker_service.session = session_manager
    session_manager.docker = docker_service
    print("After linking:")
    print(f"DockerService session: {docker_service._session}")
    print(f"SessionManager docker: {session_manager._docker}")

#this section tell entire app that any request can get it from here ...
    app.state.redis = redis_manager
    app.state.firebase = firebase_service
    app.state.docker = docker_service
    app.state.gpu = gpu_manager
    app.state.session_service = session_manager



    #this starts the background task, cuz I need the redis to get all the devices when the app starts
    load_gpu_updates = redis_manager.start_gpu_status_update()

    yield

    load_gpu_updates.clear() #this just clears everything when i shut  app


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, rate_limiter :RateLimiter ):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(self, request, call_next):
        blocked_paths = ['/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect']
        if any(request.url.path.startswith(path) for path in blocked_paths):
            return JSONResponse(

                status_code = 404,
                content={
                    "message":"Nothing to see here. Please disperse.",
                    "suggestions":"Maybe try being productive with your life ~UwU"
                }

            )
        
        await self.rate_limiter.check_rate_limit(request)
        response = await call_next(request)
        return response





app = FastAPI(lifespan=lifespan)
rate_limiter = RateLimiter(redis_manager)
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
app.add_middleware(CORSMiddleware, **CORS_CONFIG)
app.include_router(general.router)
app.include_router(docker.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)