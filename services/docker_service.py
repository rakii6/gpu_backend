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
            except docker.errors.ImageNotFound:
                return{
                    "status":"pending",
                    "message": "Image pull in progress. Please try again in a few minutes.",
                    "image": config['image']
                }                

            

            # self.redis_manager.update_gpu_status()
            print("4. Checking GPU availability")


            free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count) #call here the asiisgn_gpu, returns a list
            print(f"5. GPU check result: {free_gpu_ids}")

            #here we have a bug, we are just getting the list and not checking the failure status



            if isinstance(free_gpu_ids, dict):
                print("6. GPU check failed")
                return free_gpu_ids
            
            safe_subdomain = request.subdomain.lower()
                 #Trafix labels
            labels={
                "traefik.enable": "true",
                f"traefik.http.routers.{safe_subdomain}.entrypoints": "web",
                f"traefik.http.services.{safe_subdomain}.loadbalancer.server.port": "8888",
                f"traefik.http.routers.{safe_subdomain}.rule": f"Host(`{safe_subdomain}.indiegpu.com`)",
                "traefik.docker.network": "traefik-net"
            }
                


            try:
                print("11. Creating container...")
                print(f"Image config being used: {config}")     
                container = self.client.containers.create(  # Create container
                image=config["image"],
                environment=[*config["env"],
                             f"NVIDIA_VISIBLE_DEVICES={','.join(map(str, free_gpu_ids))}"],
                command=config["command"],
                labels=labels,
                network="traefik-net",
                device_requests=[
                    {
                        "Driver":"nvidia",
                        "Capabilities":[["gpu"]],
                        "DeviceIDs":free_gpu_ids
                    }
                ])
                print(f"12. Container created with ID: {container.id if container else 'None'}")

                allocation_errors= []
                for gpu_uuid in free_gpu_ids:
                    allocation_results = await self.gpu_manager.allocate_gpu(
                        gpu_uuid,
                        container.id,
                        request.user_id

                    )
                    if allocation_results.get('status')== 'error':
                        allocation_errors.append(allocation_results['message'])

                if allocation_errors:
                    await self._cleanup_failed_allocation(container.id, free_gpu_ids)
                    return {
                            "status": "error",
                            "message": f"GPU allocation failed: {', '.join(allocation_errors)}"
                        }    
                                    


                container.start()
                container.reload()  # Refresh container info
                


            
                container_mapping = {  
                "user_id": request.user_id,
                "container_id": container.id,
                "subdomain": request.subdomain,
                "gpu_ids":free_gpu_ids,
                "type": request.container_type}

                await self.firebase.store_container_info(request.user_id, container_mapping)# Store in Firebase


                

                return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com",
                "jupyter_token": "mysecret123"}
        
            except Exception as container_error:
                await self._cleanup_failed_allocation(container.id, free_gpu_ids)
                raise container_error
               
        except Exception as e:
            print(f"Environment creation error: {str(e)}")
            return {
            "status": "error",
            "message": str(e)
        }
            

    

    async def _cleanup_failed_allocation(self, container_id: str, gpu_ids: List[str]):
        """Cleanup resources if container creation fails"""
        try:
            # Remove container if it exists
            try:
                container = self.client.containers.get(container_id)
                container.remove(force=True)
            except:
                pass

            # Release GPU allocations
            for gpu_id in gpu_ids:
                await self.gpu_manager.release_gpu(gpu_id)

        except Exception as e:
            print(f"Cleanup error: {str(e)}")

          
            
            
           
            
            # container = self.client.containers.create(**container_config)
           


           
            
           

          

            
            

            

        