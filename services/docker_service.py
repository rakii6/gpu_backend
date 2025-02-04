import docker
import threading
from typing import Dict, Any, List
from fastapi import BackgroundTasks
import docker.errors
from schemas.docker import ContainerRequest, ContainerResponse
from services.gpu_manager import GPUManager
from .firebase_service import FirebaseService
from .redis import RedisManager
from .port import PortManager
import GPUtil

class DockerService:
    
    docker_client = docker.from_env()
    
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

    def __init__(self, gpu_manager: GPUManager, 
                 firebase_service: FirebaseService,
                   redis_manager: RedisManager): #here I am passing the class module as params cuz I need access to their methods
        self.firebase = firebase_service
        self.client = DockerService.docker_client       
        self.gpu_manager = gpu_manager
        self.redis = self.gpu_manager.redis
        self.redis_manager = redis_manager
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
        
  



    async def create_user_environment(self,request: ContainerRequest,  background_tasks: BackgroundTasks):
        

        try:
            
            
            # Validate container type
            if request.container_type not in self.IMAGE_CONFIG:
                print(f"2. Container type {request.container_type} not in config")
                return {
                    "status": "error",
                    "message": f"Unsupported container type: {request.container_type}"
                }

            # Get container from the config
            print(f"3. Using config for {request.container_type}")
            config = self.IMAGE_CONFIG[request.container_type].copy()

            try:
                print(f"checking for image:{config['image']}")
                self.client.images.get(config["image"])
                image_ready=True
                print("image not found locally")
            except docker.errors.ImageNotFound:
                image_ready=False
                print("image not found local, pulling")
                background_tasks.add_task(self.client.images.pull(config["image"]))
                return{
                    "status":"pending",
                    "message": "Image pull in progress. Please try again in a few minutes.",
                    "image": config['image']
                }                

            if image_ready:

            # self.redis_manager.update_gpu_status()
                print("4. Checking GPU availability")


                free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count) #call here the asiisgn_gpu, returns a list
                print(f"5. GPU check result: {free_gpu_ids}")

            #here we have a bug, we are just getting the list and not checking the failure status



            if isinstance(free_gpu_ids, dict) and 'status' in free_gpu_ids:
                print("6. GPU check failed")
                return free_gpu_ids
            
            print("7. Proceeding with container creation")    
            safe_subdomain = request.subdomain.lower()
            print(f"8. Using subdomain: {safe_subdomain}")
                 #Trafix labels
            labels={
                "traefik.enable": "true",
                f"traefik.http.routers.{safe_subdomain}.entrypoints": "web",
                f"traefik.http.services.{safe_subdomain}.loadbalancer.server.port": "8888",
                f"traefik.http.routers.{safe_subdomain}.rule": f"Host(`{safe_subdomain}.indiegpu.com`)",
                "traefik.docker.network": "traefik-net"
            }
            print("9. Created labels")
                
            extracted_gpu = free_gpu_ids[:request.gpu_count]
            print(f"10. Selected GPUs: {extracted_gpu}")


            try:
                print("11. Creating container...")    # Create container
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
                print(f"12. Container created with ID: {container.id}")

                for gpu_uuid in extracted_gpu:
                    print(f"13. Marking GPU {gpu_uuid} as extracted")
                    await self.redis_manager.mark_extracted_gpu(gpu_uuid,container.id,request.user_id)
                                    


                #call the redismanager to update_gpu(extracted_gpu, container.id, ContainerRequest.user_id)
                print("14. Starting container")
                container.start()
                container.reload()  # Refresh container info
                # print(f"Container Networks: {container.attrs['NetworkSettings']['Networks']}")
                # print(f"Container Labels: {container.labels}")
                # print(f"Container status: {container.status}")
                # print("Container logs:")
                # print(container.logs().decode('utf-8'))
                print("15. Creating container mapping")

                # monitor_container = threading.Thread(target=clean_up_resource, arg=(container.id))

                # container data for Firebase
            
                container_mapping = {  
                "user_id": request.user_id,
                "container_id": container.id,
                "subdomain": request.subdomain,
                "gpu_ids":extracted_gpu,
                "type": request.container_type}

                print("16. Storing in Firebase")
                await self.firebase.store_container_info(request.user_id, container_mapping)# Store in Firebase


                

                return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com",
                "jupyter_token": "mysecret123"}
        
            except Exception as container_error:
                print(f"Container creation error: {container_error}")
           
            
                return {
                "status": "error",
                "message": f"Container creation failed: {str(container_error)}"
            }
        except Exception as e:
            print(f"Environment creation error: {str(e)}")
            return {
            "status": "error",
            "message": str(e)
        }
            

    # async def clean_up_resource(self, id:str):
    #     try:
                
    #         container = self.client.containers.get(id)

    #         while True:
    #             container.reload()
    #             status =container.status
    #             health = container.attrs["State"].get("Health",{}).get("Status","no health check")
    #             dead = container.attrs["State"].get("Dead", False)

    #             print(f"Container {id} - Status: {status}, Health:{health}")

    #             if status != 'running' or health =="unhealthy":
                    
           
           

          
            
            
           
            
            # container = self.client.containers.create(**container_config)
           


           
            
           

          

            
            

            

        