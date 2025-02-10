from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import docker,general
from config.setting import CORS_CONFIG
from services.gpu_manager import GPUManager
from services.redis import RedisManager
from services.firebase_service import FirebaseService
from services.docker_service import DockerService
from services.log_manager import Log_manager
@asynccontextmanager
async def lifespan(app:FastAPI):
    redis_manager = RedisManager() #only one universal redis client connection is created

    gpu_manager= GPUManager(redis_manager) #gpumanager consumes this redis client for his own purpose


    firebase_service = FirebaseService() #only onefirebase client is created.
    docker_service= DockerService(gpu_manager,firebase_service, redis_manager) #docker manager consumes gpu manger for his own purpose



#this section tell entire app that any request can get it from here ...
    app.state.redis = redis_manager
    app.state.firebase = firebase_service
    app.state.docker = docker_service
    app.state.gpu = gpu_manager




    #this starts the background task, cuz I need the redis to get all the devices when the app starts
    load_gpu_updates = redis_manager.start_gpu_status_update()

    yield

    load_gpu_updates.clear() #this just clears everything when i shut  app



app = FastAPI(lifespan=lifespan)

app.add_middleware(CORSMiddleware, **CORS_CONFIG)

app.include_router(general.router)
app.include_router(docker.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)