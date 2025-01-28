import docker
from typing import Dict, Any, List
from schemas.docker import ContainerRequest, ContainerResponse
from services.gpu_manager import GPUManager
from .firebase_service import FirebaseService
from .port import PortManager
import GPUtil

class DockerService:
    # Configuration at class level
    IMAGE_CONFIG = {
        "jupyter": {
            "image": "jupyter/datascience-notebook",
            "base_port": 8888,
            "env": [
                "JUPYTER_ENABLE_LAB=yes",
                "JUPYTER_TOKEN=mysecret123"
            ],
            "command": "start-notebook.sh --NotebookApp.token=mysecret123 --NotebookApp.ip=0.0.0.0 --NotebookApp.allow_origin='*'"
                
            
           
        },
        "pytorch": {
            "image": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            "base_port": 8888,
            "env": ["JUPYTER_TOKEN=mysecret123"],
            "command": "/bin/bash -c 'pip install jupyter jupyterlab && python3 -m jupyter notebook --ip=0.0.0.0 --allow-root --NotebookApp.token=mysecret123 --NotebookApp.allow_origin=* --port=8888'"
            
           
        },
        "tensorflow": {
            "image": "tensorflow/tensorflow:latest-gpu",
            "base_port": 8888,
            "env": ["JUPYTER_TOKEN=mysecret123",
                    "JUPYTER_ENABLE_LAB=yes"],
            
            "command": "/bin/bash -c 'pip install jupyter jupyterlab && python3 -m jupyter lab --ip=0.0.0.0 --port=8888 --allow-root --NotebookApp.token=mysecret123 --no-browser'"
            
            
        }
    }

    def __init__(self, firebase_service: FirebaseService):
        self.firebase = firebase_service
        self.client = docker.from_env()
        self.gpu_manager = GPUManager()
        self.container_store = {}
        
        try:
            self.client.networks.get("traefik-net")
        except:
            self.client.networks.create("traefik-net", driver="bridge")


    async def check_docker(self) -> Dict:
        try:
            containers = self.client.containers.list()
            return {
                "status": "connected",
                "containers": len(containers)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    async def run_container(self, image: str = 'alpine', command: str = 'echo hello world', detach: bool = True) -> Dict:
        try:
            print("Starting container creation...")
            container = self.client.containers.create(
                image=image, 
                command=command
            )
            container.start()
            self.container_store['latest'] = container.id
            return {
                "status": "success",
                "container_id": container.id
            }
        except Exception as e:
            return {
                "status": "Failed to start container",
                "message": str(e)
            }
        
  



    async def create_user_environment(self,request: ContainerRequest):
        

        try:

            
            # Validate container type
            if request.container_type not in self.IMAGE_CONFIG:
                return {
                    "status": "error",
                    "message": f"Unsupported container type: {request.container_type}"
                }

            # Get container from the config
            config = self.IMAGE_CONFIG[request.container_type].copy()
            free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count) #call here the asiisgn_gpu, returns a list
            #here we have a bug, we are just getting the list and not checking the failure status
            if isinstance(free_gpu_ids, list):
                safe_subdomain = request.subdomain.lower()
                 #Trafix labels
                labels={
                "traefik.enable": "true",
                f"traefik.http.routers.{safe_subdomain}.entrypoints": "web",
                f"traefik.http.services.{safe_subdomain}.loadbalancer.server.port": "8888",
                f"traefik.http.routers.{safe_subdomain}.rule": f"Host(`{safe_subdomain}.indiegpu.com`)",
                "traefik.docker.network": "traefik-net"
            }
                print(f"Creating container with labels: {labels}")
                print(f"Using GPU IDs: {free_gpu_ids}")
                extracted_gpu = free_gpu_ids[:request.gpu_count]


                 # Create container
                container = self.client.containers.create(
                image=config["image"],
                environment=[*config["env"],
                             f"NVIDIA_VISIBLE_DEVICES={','.join(map(str, extracted_gpu))}"],
                command=config["command"],
                labels=labels,
                network="traefik-net",
                device_requests=[
                    {
                        "Driver":"nvidia",
                        "Capabilities":[["gpu"]],
                        "DeviceIDs":extracted_gpu
                    }
                ])

                container.start()
                container.reload()  # Refresh container info
                print(f"Container Networks: {container.attrs['NetworkSettings']['Networks']}")
                print(f"Container Labels: {container.labels}")
                print(f"Container status: {container.status}")
                print("Container logs:")
                print(container.logs().decode('utf-8'))

                # container data for Firebase
            
                container_mapping = {  
                "user_id": request.user_id,
                "container_id": container.id,
                "subdomain": request.subdomain,
                "gpu_ids":extracted_gpu,
                "type": request.container_type}

                await self.firebase.store_container_info(request.user_id, container_mapping)# Store in Firebase

                return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com",
                "jupyter_token": "mysecret123"}
        
        except Exception as e:
            print(f"Error creating environment: {str(e)}")
           
            
            return {
                "status": "error",
                "message": str(e)
            }
            

                

           
           

          
            
            
           
            
            # container = self.client.containers.create(**container_config)
           
            
           
            
           

          

            
            

            

        