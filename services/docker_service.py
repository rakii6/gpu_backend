import docker
from typing import Dict, Any, List, Optional
from fastapi import BackgroundTasks
import docker.errors
from schemas.docker import ContainerRequest, ContainerResponse
from services.gpu_manager import GPUManager
from .firebase_service import FirebaseService
from .redis import RedisManager
from datetime import datetime
from firebase_admin import firestore
import pytz, arrow
import os

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
        # self.redis = self.gpu_manager.redis
        self.redis_manager = redis_manager
        self.session_db = redis_manager.get_database(1)
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
        container = None
        try:
            print(f"Starting container creation for user: {request.user_id}, type: {request.container_type}")
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
            
            print("Getting container config...")
            config = self.IMAGE_CONFIG[request.container_type].copy()

            try:
                print("Checking if image exists...")
                self.client.images.get(config["image"])
            except docker.errors.ImageNotFound:
                return{
                    "status":"pending",
                    "message": "Image pull in progress. Please try again in a few minutes.",
                    "image": config['image']
                }                
            print(f"Checking GPU availability for {request.gpu_count} GPUs...")
            free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count) #call here the asiisgn_gpu, returns a list
            resources = self.calculate_resource_limit(request.gpu_count, request.container_type)
            #here we have a bug, we are just getting the list and not checking the failure status
            
            if isinstance(free_gpu_ids, dict):
                return free_gpu_ids
            
            print(f"Found available GPUs: {free_gpu_ids}")
            safe_subdomain = request.subdomain.lower()
            print(f"Using subdomain: {safe_subdomain}")
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
                volumes=self.get_user_volumes(request.user_id),
                environment=[*config["env"],
                             f"NVIDIA_VISIBLE_DEVICES={','.join(map(str, free_gpu_ids))}"],
                          
                command=config["command"],
                labels=labels,
                network="traefik-net",
                mem_limit=f"{resources['ram_gb']}g", #do not userr mem_reservation it hard codes the RAM allocation
                cpu_count=resources['cpu_count'],
                device_requests=[
                    {
                        "Driver":"nvidia",
                        "Capabilities":[["gpu"]],
                        "DeviceIDs":free_gpu_ids
                    }
                ])
                if not container:
                    return {
                        "status": "error",
                        "message": "Container creation failed - Docker returned None"
                            }
                
                print(f"Container created successfully: {container.id}")




                allocation_errors= [] 
                for gpu_uuid in free_gpu_ids:#this section is to tell the gpu manager, that contaier with gpuuid and user_id to be updated in redis
                    allocation_results = await self.gpu_manager.allocate_gpu( 
                        gpu_uuid,
                        container.id,
                        request.user_id

                    )
                    if allocation_results.get('status')== 'error':
                        allocation_errors.append(allocation_results['message'])
                print("gpu allocated success")

                if allocation_errors:
                    await self._cleanup_failed_allocation(container.id, free_gpu_ids)
                    return {
                            "status": "error",
                            "message": f"GPU allocation failed: {', '.join(allocation_errors)}"
                        }    
                 
                container.start()
                container.reload()  # Refresh container info
                print("container starting")

                dt = arrow.utcnow()
                expired_time = dt.shift(hours=request.duration)
                

                container_data = {  
                "user_id": request.user_id,
                "container_id": container.id,
                "subdomain": request.subdomain,
                "gpu_count":len(free_gpu_ids),
                "gpu_ids":free_gpu_ids,
                "type": request.container_type,
                "created_at":dt.datetime,
                "expires_at":expired_time.datetime,
                "status":container.status
                }
                print("contianer mapped")
                

                session_result = await self._session.start_session(
                    user_id=request.user_id,
                    container_id = container.id,
                    duration_hours=request.duration, #needs changeing
                    payment_status=True,
                )
                print("session result achecived")
                await self.firebase.store_container_info(container.id, container_data)# Store in Firebase

                return {
                "status": "success",
                "container_id": container.id,
                "access_url": f"{request.subdomain}.indiegpu.com",
                "jupyter_token": "mysecret123",
                "session":session_result}
        
            except Exception as container_error:
                print(f"Container creation error: {str(container_error)}")
                if container:
                    await self._cleanup_failed_allocation(container.id, free_gpu_ids)
                return {
                "status": "error",
                "message": f"Container creation failed: {str(container_error)}"
            }
               
        except Exception as e:
            print(f"Environment creation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
            "status": "error from enviromnet creation",
            "message": str(e)
        }

    def get_user_volumes(self, user_id):
        user_data_dir = f"/home/rakii06/user_data/{user_id}"

        try:
            os.makedirs(user_data_dir, exist_ok=True)
            os.makedirs(f"{user_data_dir}/logs", exist_ok=True)
            os.makedirs(f"{user_data_dir}/data", exist_ok=True)
        except PermissionError:
            print(f"Permission error creating {user_data_dir} - check permissions")
            return {}
        except Exception as e:
            print(f"Error creating user directory: {str(e)}")
            return {}
    
        return {
            user_data_dir:{'bind':'/app', 'mode':'rw'},
            '/home/rakii06/Docker-python/DockerFiles/logs':{'bind':'/app/logs','mode':'rw'},
            '/home/rakii06/Docker-python/DockerFiles/config':{'bind':'/app/config', 'mode':'ro'},
            '/home/rakii06/Docker-python/DockerFiles/static':{'bind':'/app/static','mode':'ro'}
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
            print(f"CLEANUP: Starting cleanup for container {container_id}, ")
            gpu_ids = []
            try:
                print(f"CLEANUP: Getting container from Docker API")
                container = self.client.containers.get(container_id)
                print(f"CLEANUP: Container found with status: {container.status}")
                container_info = container.attrs
                device_requests = container_info["HostConfig"].get("DeviceRequests", [])
                for devices in device_requests:
                    if devices.get("Driver") =="nvidia":
                        gpu_ids = devices.get('DeviceIDs',[])
                    
                print(f"CLEANUP: Stopping container {container_id}")
                container.stop(timeout=15)
                print(f"CLEANUP: Container stopped, now removing")
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
                await self.firebase.update_container_status( container_id, "terminated", user_id)
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
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)

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
                for session_key in self.session_db.scan_iter("session:*"):
                    session_data = self.session_db.hgetall(session_key)
                    print(f"Checking GPU: {session_key}")

                    if session_data:
                        container_id_value = session_data.get(b'container_id',b'').decode('utf-8')
                        print(f"Stored container ID: {container_id_value}")
                        if container_id_value == container_id:

                            new_state={
                            "status":"paused",
                            "container_id": container_id,
                            "user_id": user_id,
                            "allocated_at": session_data.get(b'allocated_at', b'').decode('utf-8'),
                            "paused_at":current_time.isoformat()
                        }
                            self.session_db.hset(session_key,  mapping = new_state)
                            print(f"Updated state for GPU {session_key}") 
                        

                await self.firebase.update_container_status(container_id, "paused", user_id)
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
                for session_key in self.session_db.scan_iter("gpu:*"):
                    session_data = self.session_db.hgetall(session_key)
                    if session_data:
                        container_id_value = session_data.get(b'container_id',b'').decode('utf-8')
                        if container_id_value == container_id:
                            new_state={
                                "status":"in_use",
                                "container_id": container_id,
                                "user_id": user_id,
                                "allocated_at": session_data.get(b'allocated_at', b'').decode('utf-8')
                                }
                            self.session_db.hset(session_key, mapping=new_state)
                await self.firebase.update_container_status(container_id, "active", user_id) 

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
    def calculate_resource_limit(self, gpu_count:int, container_type:str):
        base_resources = {
            "ram_per_gpu":16,
            "cpu_per_gpu":3,
            "storage_per_gpu":100
        }

        type_multipliers={
            "jupyter":{"ram":1.0, "cpu":1.0},
            "pytorch":{"ram":1.2, "cpu":1.0},
            "tensorflow":{"ram":1.2, "cpu":1.1}
        }

        multiplier= type_multipliers.get(container_type, {"ram": 1.0, "cpu": 1.0})

        return{
            "ram_gb":int(base_resources["ram_per_gpu"]*gpu_count*multiplier["ram"]),
            "cpu_count":int(base_resources["cpu_per_gpu"]*gpu_count*multiplier["cpu"]),
            "storage_gb":int(base_resources["storage_per_gpu"]*gpu_count)
        }
    async def monitor_container_resources(self):
        """For user and especailly admin"""
        # please don't ask me what and how I calculated I just copy pasted from someone eles's code
        container_stats =[]
        try:
            containers = self.client.containers.list()
            for container in containers:
                try:
                    stats =container.stats(stream=False)

                    info = container.attrs

                    mem_limit = info['HostConfig'].get('Memory', 0) / (1024**3)  # Convert to GB
                    cpu_count = info['HostConfig'].get('CpuCount', 0)
                
                # Extract current usage
                    mem_usage = stats['memory_stats'].get('usage', 0) / (1024**3)  # Convert to GB
                
                # CPU usage is more complex as it's a percentage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']
                    
                    if system_delta >0:
                        cpu_usage = (cpu_delta/system_delta)*100.0
                    else:
                        cpu_usage = 0

                    container_stats.append({
                    'container_id': container.id,
                    'name': container.name,
                    'memory_usage_gb': round(mem_usage, 2),
                    'memory_limit_gb': round(mem_limit, 2),
                    'memory_percent': round((mem_usage / mem_limit * 100) if mem_limit > 0 else 0, 2),
                    'cpu_usage_percent': round(cpu_usage, 2),
                    'cpu_count': cpu_count
                })
                    if mem_usage > 0.85 * mem_limit and mem_limit > 0:

                        print(f"WARNING: Container {container.id} is using {round(mem_usage, 2)}GB of {round(mem_limit, 2)}GB RAM ({round(mem_usage/mem_limit*100, 2)}%)")
                        #here I need to send a warning to the admin or the user
                except Exception as e:
                    print(f"Error getting stats for container {container.id}: {str(e)}")
                    continue   
            return container_stats  
        except Exception as e:
            print(f"Error monitoring containers: {str(e)}")
            return []      

    async def start_resource_monitoring(self):
        """just a background task to start periodically"""
        import asyncio

        async def monitor_loop():
            while True:
                try:
                    stats = await self.monitor_container_resources()
                    totat_mem_percent = 0
                    total_cpu_percent = 0

                    if stats:
                        total_containers = len(stats)
                        for stat in stats:
                            totat_mem_percent += stat['memory_percent']
                            total_cpu_percent += stat['cpu_usage_percent']
                        avg_mem_percent  = totat_mem_percent / total_containers
                        avg_cpu_percent = total_cpu_percent/total_containers

                        print(f"Resource monitor: {total_containers} containers running")
                        print(f"Average memory usage: {avg_mem_percent:.2f}%, Average CPU usage: {avg_cpu_percent:.2f}%")
                    await asyncio.sleep(300)
                except Exception as e:
                    print(f"error in monitoring loop {str(e)}")
                    await asyncio.sleep(60) #retry on error
                    
        asyncio.create_task(monitor_loop())

        
                    





          
            
      
           
            
         
           


           
            
           

          

            
            

            

        