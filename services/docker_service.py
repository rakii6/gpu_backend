import docker
from typing import Dict, Any,List
from schemas.docker import ContainerRequest
from .firebase_service import FirebaseService

class DockerService:
    def __init__(self, firebase_service: FirebaseService):
        self.firebase = firebase_service
        self.client = docker.from_env()
        self.container_store = {}

    async def check_docker(self) -> Dict:
        try:
            containers = self.client.containers.list()
            return{"status":"connected","containers":len(containers)}
        except Exception as e:
            return {"status":"error","message":str(e)}

    async def run_container(self, image:str='alpine', command:str='echo hello world', detach: bool=True) -> Dict:
        try:
            print("Starting container creation...")
            
            container= self.client.containers.create(
                image=image, 
                command=command)

            container.start()

            self.container_store['latest']=container.id

            return{
                "status":"success",
                "container_id":container.id
            }      
        except Exception as e:
            return{"status":"Failed to start container",
                "message":str(e)}
        
    async def create_user_environment(self, request: ContainerRequest):
        try:
            image_config ={
                "jupyter":{
                    "image":"jupyter/datascience-notebook",
                    "port":8888
                },
                "pytorch":{
                    "image":"pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
                    "port":8891
                },
                "tensorflow":{
                    "image":"tensorflow/tensorflow:latest-gpu",
                    "port":8892
                }
            }

            config = image_config[request.container_type]

            container = self.client.containers.create(
                image=config["image"],
                ports={'8888/tcp': 8888},
                environment=[
                    "JUPYTER_ENABLE_LAB=yes",
                    "JUPYTER_TOKEN=mysecret123"
                ],
                device_requests=[
                    docker.types.DeviceRequest(
                        count=-1,
                        capabilities=[['gpu']]
                    )
                ]
            )
            container.start()

            container_mapping ={
                "user_id":request.user_id,
                "container_id": container.id,
                "subdomain":request.subdomain,
                "port":config["port"]
            } #for storage into the firebase 

            await self.firebase.store_container_info(request.user_id, container_mapping)



            return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com"
            }
        
        except Exception as e:
            return{
                "status":"Failed",
                "Message":str(e)
            }
            






    
