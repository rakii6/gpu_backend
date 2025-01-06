from  fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import docker

app = FastAPI()

client = docker.from_env()
container_store = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*.indiegpu.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
async def root():
    return {"Message":"Hello World"}

@app.get('/{item}')
async def item_name(item: str):
    return {"Message":item}

@app.get('/docker/check')
async def checkDocker():
    try:

        containers = client.containers.list()
        return {"status": "connected",
                "containers":len(containers)}
    except Exception as e:
        return {"status":"error",
                "message":str(e)}
  
@app.post('/docker/run')
async def run_container():
    try:
        container = client.containers.run('alpine', 'echo hello world', detach=True)
        container_store['latest']= container.id
        return{
            "status":"success",
            "container_id":container.id
        }
    except Exception as e:
        return{
             "status":"success",
            "message":str(e)        }



@app.get('/docker/latest/output')
async def get_latest_output():
    try:
        if 'latest' not in container_store:
            return {"status":"error","message": "No container found"}

        container = client.containers.get(container_store['latest'])
        output = container.logs().decode('utf-8')
        return {
            "status":"success nigga",
            "output":output
        }
    
    except Exception as e:
        return{
            "status":"",
            "message":str(e)
        }
    
@app.get('/docker/containers/all')
async def list_all_containers():
    try:
        containers = client.containers.list()
        container_list = []

        for container in containers:
            container_info = {
                "id":container.id,
                "name":container.name,
                "status":container.status
            }

            container_list.append(container_info)

        return{
            "status":"success",
            "containers":container_list
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post('/docker/containers/stop-all')
async def stop_all_containers():
    try:
        containers = client.containers.list()
        for container in containers:
            container.stop()
        return {
            "status": "success",
            "message": f"Stopped {len(containers)} containers"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
    
@app.post('/docker/start-nginx')
async def start_nginx():
    try:
        container = client.containers.run(
            'nginx',
            detach=True,
            ports={'80/tcp': 8090})
        
        container_store = container.id
        return{
            "status":"succcess nigga",
            "container_id":container.id,
            "how_to_access": "Open http://indiegpu.com:8090 in your browser"

        }
    except Exception as e:
        return{
            "status":"Error",
            "message":str(e)
        }

@app.get('/docker/container/inspect/{container_id}')
async def inspect_container(container_id: str):
    try:
        container = client.containers.get(container_id)
        return {
            "status": "success",
            "container_info": {
                "status": container.status,
                "ports": container.attrs['HostConfig']['PortBindings'],
                "name": container.name
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post('/docker/start-jupyter')
async def start_jupyter():
    try:
        container = client.containers.run(
            'jupyter/datascience-notebook',
             detach=True,
              ports={'8888/tcp': 8888},
              environment=[
                "JUPYTER_ENABLE_LAB=yes",  # Enable JupyterLab interface
                "JUPYTER_TOKEN=mysecret123"  # Set a security token
            ],
             volumes={
                '/home/rakii06/project-imagesgi': {  # Replace with your desired host path
                    'bind': '/home/jovyan/work',
                    'mode': 'rw'
                }
             }
        )
        container_store['jupyter'] = container.id
        import time
        time.sleep(5)

        logs = container.logs().decode('utf-8')

        return {
            "status": "success",
            "container_id": container.id,
            "access_url": "jupyter.indiegpu.com",
            "token": "mysecret123",
            "message": "Jupyter notebook is ready. Use the token above to login."
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
    

@app.get('/docker/jupyter/status')
async def get_jupyter_status():
    try:
        if 'jupyter' not in container_store:
            return {"status": "not_running"}
            
        container = client.containers.get(container_store['jupyter'])
        
        return {
            "status": "running",
            "container_id": container.id,
            "container_status": container.status,
            "url": "http://jupyter.indiegpu.com"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }





if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)



# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from .app.config import cors_config
# from .app.api import docker, general

# app = FastAPI()

# app.add_middleware(CORSMiddleware, **cors_config)

# app.include_router(general.router)
# app.include_router(docker.router)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)