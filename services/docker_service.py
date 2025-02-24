import docker
import threading
from typing import Dict, Any, List, Optional
from fastapi import BackgroundTasks
import docker.errors
from schemas.docker import ContainerRequest, ContainerResponse
from services.gpu_manager import GPUManager
from .service_types import SessionManager
from .firebase_service import FirebaseService
from .redis import RedisManager
from .port import PortManager
from datetime import datetime
import pytz

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

    def __init__(self, gpu_manager: GPUManager, firebase_service: FirebaseService, redis_manager: RedisManager,session_manager=None): #here I am passing the class module as params cuz I need access to their methods
        self.firebase = firebase_service
        self.client = DockerService.docker_client       
        self.gpu_manager = gpu_manager
        self.redis = self.gpu_manager.redis
        self.redis_manager = redis_manager
        self._session = session_manager
        self.container_store = {}


        
        try:
            self.client.networks.get("traefik-net")
        except:
            self.client.networks.create("traefik-net", driver="bridge")

    @property
    def session(self):
            return self._session
    @session.setter
    def session(self, value):
            self._session = value

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
            # print("Starting container creation...")
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
            print(f"Current session state: {self._session}")
            print(f"Has session attribute: {'_session' in self.__dict__}")
            if not hasattr(self, '_session') or self._session is None:
                    print("waring session manager not Init yet")
                    return{
                        "status":"error",
                        "message":"session mnager not initiated propelly yet"
                    }
            if request.container_type not in self.IMAGE_CONFIG:
                return {
            
                    "status": "error",
                    "message": f"Unsupported container type: {request.container_type}"
                }
            
            
            config = self.IMAGE_CONFIG[request.container_type].copy()

            try:
                self.client.images.get(config["image"])
            except docker.errors.ImageNotFound:
                return{
                    "status":"pending",
                    "message": "Image pull in progress. Please try again in a few minutes.",
                    "image": config['image']
                }                
        
            free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count) #call here the asiisgn_gpu, returns a list

            #here we have a bug, we are just getting the list and not checking the failure status
            
            if isinstance(free_gpu_ids, dict):
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

                allocation_errors= [] 
                for gpu_uuid in free_gpu_ids:#this section is to tell the gpu manager, that contaier with gpuuid and user_id to be updated in redis
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


                session_result = await self._session.start_session(
                    user_id=request.user_id,
                    container_id = container.id,
                    duration_hours=request.duration,
                    payment_status=True
                )

                await self.firebase.store_container_info(request.user_id, container_mapping)# Store in Firebase

                return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com",
                "jupyter_token": "mysecret123",
                "session":session_result}
        
            except Exception as container_error:
                await self._cleanup_failed_allocation(container.id, free_gpu_ids)
                raise container_error
               
        except Exception as e:
            # print(f"Environment creation error: {str(e)}")
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


    async def cleanup_container(self,container_id: str, user_id:str)->Dict:
        try:
            gpu_ids = []
            try:

                container = self.client.containers.get(container_id)
                print(f"container is populated")
                container_info = container.attrs
                device_requests = container_info["HostConfig"].get("DeviceRequests", [])
                for devices in device_requests:
                    if devices.get("Driver") =="nvidia":
                        gpu_ids = devices.get('DeviceIDs',[])
                    

                container.stop(timeout=15)
                container.remove()
            except docker.errors.NotFound:
                return{
                    "status":"error",
                    "message":f"container{container_id} not found"
                }

            gpu_release_errors=[]       
            for gpu_id in gpu_ids:
                try:
                    await self.gpu_manager.release_gpu(gpu_id)
                except Exception as gpu_error:
                        gpu_release_errors.append(f"Error releasing GPU {gpu_id}: {str(gpu_error)}")
                        return{
                                "message":f"Warning: {gpu_release_errors[-1]}"
                                }
       
                ist = pytz.timezone('Asia/Kolkata')
                ist_time = datetime.now(ist)

            try:
                await self.firebase.update_container_status(user_id, container_id, "terminated", ist_time)
                print("about to hit the cleanup session")
                result = await self._session.cleanup_expired_session(container_id)

                return {
                "status": "success",
                "message": "Container cleaned up successfully",
                "result_clean":result
            }

            except Exception as e:
                   print(f"Firebase update error: {str(e)}")
            
        
        
            return{
            "status":"success",
            "message":f"docker container has been stopped. Take care."
            }
                
        except Exception as e:
            return{
                "error":"Error from Cleanup Container section",
                "message":str(e)
            }

    async def pause_container(self,container_id:str, user_id:str):

        try:

            try:
                container_to_pause = self.docker_client.containers.get(container_id)
                if not container_to_pause:
                    return{
                    "status":"error",
                    "Message":"container with that ID not found"
                }
                container_to_pause.reload()
                print(f'contianer paused')
                if container_to_pause.status == "paused":
                    return{
                        "status":"error",
                        "message":"its already paused bruh"
                    }
                
                container_to_pause.pause()

            except docker.errors.NotFound:
                return {
                "status": "error ",
                "message": f"Container {container_id} not found"
            }
            except docker.errors.APIError as e:
                return {
                "status": "error",
                "message": f"Error pausing container: {str(e)}"
                }
                
            
            try: 
                for gpu_key in self.redis.scan_iter("gpu:*"):
                    gpu_data = self.redis.hgetall(gpu_key)
                    print(f"Checking GPU: {gpu_key}")

                    if gpu_data:
                        container_id_value = gpu_data.get(b'container_id',b'').decode('utf-8')
                        print(f"Stored container ID: {container_id_value}")
                        if container_id_value == container_id:

                            new_state={
                            "status":"paused",
                            "container_id": container_id,
                            "user_id": user_id,
                            "allocated_at": gpu_data.get(b'allocated_at', b'').decode('utf-8')
                        }
                            self.redis.hset(gpu_key,  mapping = new_state)
                            print(f"Updated state for GPU {gpu_key}") 
                        

                await self.firebase.update_container_status(user_id, container_id, "paused")
                return {
                "status": "success",
                "message": f"Container {container_id} paused successfully"
                }
            
            except Exception as e:
                return{
                    "status":"error",
                    "message":str(e)
                }
        except Exception as e:
            return{
                "status":"erroor",
                "message":str(e)
            }

    async def restart_container(self, container_id:str, user_id:str):
        try:

            try:
                container_to_revive = self.docker_client.containers.get(container_id)

                if not container_to_revive:
                    return{
                        "status":"error",
                        "message":"container with that ID not found"
                    }
                if container_to_revive.status == "running":
                    return{
                        "status":"error",
                        "message":"its already running bruh"
                    }
                
                container_to_revive.reload()
                container_to_revive.stop()
                container_to_revive.start()
            except docker.errors.NotFound:
                return {
                "status": "error",
                "message": f"Container {container_id} not found"
                }
            except docker.errors.APIError as e:
                return {
                "status": "error",
                "message": f"Error restarting container: {str(e)}"
                }
            
            try:
                for gpu_key in self.redis.scan_iter("gpu:*"):
                    gpu_data = self.redis.hgetall(gpu_key)
                    if gpu_data:
                        container_id_value = gpu_data.get(b'container_id',b'').decode('utf-8')
                        if container_id_value == container_id:
                            new_state={
                                "status":"in_use",
                                "container_id": container_id,
                                "user_id": user_id,
                                "allocated_at": gpu_data.get(b'allocated_at', b'').decode('utf-8')
                                }
                            self.redis.hset(gpu_key, mapping=new_state)
                await self.firebase.update_container_status(user_id, container_id, "running") 

                return{
                    "status": "success",
                    "message": f"Container {container_id} restarted successfully"
                }
            except Exception as e:
                return{
                    "status":"error",
                    "message":str(e)
                }
        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }

                    
                        


                    





          
            
      
           
            
         
           


           
            
           

          

            
            

            

        