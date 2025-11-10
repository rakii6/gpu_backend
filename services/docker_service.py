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
            "image": "indiegpu/jupyter:v7",
            "command":None,
            "base_port": 8888,
            "env": [
                "JUPYTER_ENABLE_LAB=yes",
                "JUPYTER_TOKEN=mysecret123"
            ],
            "command": "start-notebook.sh --NotebookApp.token=mysecret123 --NotebookApp.ip=0.0.0.0 --NotebookApp.allow_origin='*'"
                
            
           
        },
        "pytorch": {
            "image": "indiegpu/jupyter:v7",
            "command":None,
            "base_port": 8888,
            "env": ["JUPYTER_TOKEN=mysecret123"],
            "command": "/bin/bash -c 'pip install jupyter jupyterlab && python3 -m jupyter notebook --ip=0.0.0.0 --allow-root --NotebookApp.token=mysecret123 --NotebookApp.allow_origin=* --port=8888'"
            
           
        },
        "tensorflow": {
            "image": "indiegpu/jupyter:v7",
            "command":None,
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

    async def test_persistence(self, user_id: str):
        """Test if files persist between container runs"""
        import os
        
        # 1. Create user directory in your home (has permissions)
        user_dir = f"/home/rakii06/indiegpu_storage/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # 2. Write a test file
        test_file = f"{user_dir}/persistence_test.txt"
        with open(test_file, "w") as f:
            f.write("Hello from TARS! This file should survive container restarts!")
        
        # 3. Run container and check if file is visible
        try:
            output = self.client.containers.run(
                "ubuntu:latest",
                command=["/bin/bash", "-c", "ls -la /workspace && echo '--- FILE CONTENT ---' && cat /workspace/persistence_test.txt"],
                volumes={user_dir: {'bind': '/workspace', 'mode': 'rw'}},
                remove=True,
                detach=False
            )
            
            return {
                "status": "success",
                "message": "File persistence works!",
                "output": output.decode(),
                "user_dir": user_dir
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
        

    async def create_user_environment(self,request: ContainerRequest):
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
            free_gpu_ids = await self.gpu_manager.check_gpu_availability(request.gpu_count,request.user_id) #call here the asiisgn_gpu, returns a list
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
            user_volumes = self.get_user_volumes(request.user_id)
            if not user_volumes:
                return{
                    "status":"error",
                    "message":"failed to create user Storage directories"
                }

            try:
                container = self.client.containers.create(  # Create container
                image=config["image"],
                volumes=user_volumes,
                environment=[*config["env"],
                             f"NVIDIA_VISIBLE_DEVICES={','.join(map(str, free_gpu_ids))}"],
                          
                command=config["command"],
                labels=labels,
                network="traefik-net",
                mem_limit=f"{resources['ram_gb']}g", #do not userr mem_reservation it hard codes the RAM allocation
                memswap_limit=f"{resources['ram_gb']}g",
                cpu_count=resources['cpu_count'], 
                cpu_period=100000,
                cpu_quota=int(100000 * resources['cpu_count']),
                # pids_limit=1024,
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
        

        user_storage_base = f"/home/rakii06/jupyter_notebooks"
        user_specific_dir = f"{user_storage_base}/{user_id}"

        try:
            os.makedirs(user_specific_dir, exist_ok=True)
            welcome_content = {
                "cells":[
                    {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["#😏  Welcome to IndieGPU!\n\n## Your GPU-powered workspace is ready!"]
                    },
                    {
                        "cell_type":"code",
                        "execution_count":None,
                        "metadata":{},
                        "outputs":[],
                        "source":[
                            "import torch\n",
                            "print(f'CUDA available: {torch.cuda.is_available()}')\n",
                            "if torch.cuda.is_available():\n",
                            "    print(f'GPU: {torch.cuda.get_device_name(0)}')"
                        ]
                    }
                ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 4
            }

            import json
            with open(f"{user_specific_dir}/Welcome_to_IndieGPU.ipynb", "w") as f:
                json.dump(welcome_content, f, indent=2)

            os.chmod(user_specific_dir, 0o755)
            print(f"Created user directory: {user_specific_dir}")
        
        
        except Exception as e:
            print(f"Error creating user directory: {str(e)}")
            return {}
    
        return {
            user_specific_dir:{'bind':'/home/jovyan/work', 'mode':'rw'},
            
            }

        




    async def _cleanup_failed_allocation(self, container_id: str, gpu_ids: List[str], user_id:str=None, cost:float=None, payment_method:str=None):
        """Cleanup resources if container creation fails"""
        try:
            # Remove container if it exists
            try:
                container = self.client.containers.get(container_id)
                container.remove(force=True)
                print(f"✅ Removed failed container {container_id}")
            except docker.errors.NotFound:
                print(f"⚠️  Container {container_id} doesn't exist in Docker (expected)")
                pass
            except Exception as container_error:
                print(f"❌ Error removing container: {str(container_error)}")

            # Release GPU allocations
            for gpu_id in gpu_ids:
                 try:
                    await self.gpu_manager.release_gpu(gpu_id)
                    print(f"Released GPU {gpu_id} from cleanup section")
                 except Exception as e:
                     print(f'Error releasing GPU {gpu_id}: {str(e)}')
                 
            if user_id and cost and payment_method:
                print(f"processing refund of ${cost} for {user_id}, into the {payment_method} ")

                if payment_method == 'credits':
                    try:
                        from services.credits_service import CreditsManager
                        credit_manager = CreditsManager(self.firebase.db)

                        refund_result = await credit_manager.add_credits(user_id=user_id, amount=cost, source='refund',metadata={'container_id':container_id,'reason':'Container Allocation failure',"failure_type":'Allocation_error'})

                        if refund_result['status']=='success':
                            print(f"✅ Refunded ${cost} credits to user {user_id}")
                        else:
                            print(f"❌ Credit refund failed: {refund_result.get('message')}")  
                    except Exception as refund_error:
                        print(f"Error processing credit refund: {str(refund_error)}")
                elif payment_method == 'card':
                    # Log for manual Razorpay refund
                    print(f"MANUAL REFUND REQUIRED: User {user_id} paid ${cost} via Razorpay")
                    print(f"   Container ID: {container_id}")
                    print(f"   Action: Admin must process Razorpay refund manually")
                    
                    # TODO: You could trigger a Telegram/email notification here
                    # await self.notify_admin_manual_refund(user_id, cost, container_id)
        
            print(f"Failed allocation cleanup complete")
            
            return {
                "status": "success",
                "message": "Cleanup completed, refund processed if applicable"
            }

        except Exception as e:
            print(f"💥 Error in _cleanup_failed_allocation: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": f"Cleanup failed: {str(e)}"
            }
    
        


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
                result = await self._session.cleanup_expired_session(container_id, user_id)

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






    # async def cleanup_container(self, container_id: str, user_id: str) -> Dict:
    #     import traceback
    #     import time
        
    #     print(f"\n🔧 === DOCKER CLEANUP SERVICE START ===")
    #     print(f"📦 Target container: {container_id}")
    #     print(f"👤 Target user: {user_id}")
        
    #     try:
    #         # Step 1: Get GPU IDs before container destruction
    #         print(f"🎮 STEP 1: Getting GPU allocations for container...")
    #         gpu_ids = []
            
    #         try:
    #             container = self.client.containers.get(container_id)
    #             print(f"✅ Container found in Docker: {container.name} (Status: {container.status})")
                
    #             container_info = container.attrs
    #             device_requests = container_info["HostConfig"].get("DeviceRequests", [])
    #             print(f"🔍 Device requests found: {len(device_requests)}")
                
    #             for i, device in enumerate(device_requests):
    #                 print(f"   Device {i}: Driver={device.get('Driver')}, DeviceIDs={device.get('DeviceIDs', [])}")
    #                 if device.get("Driver") == "nvidia":
    #                     gpu_ids = device.get('DeviceIDs', [])
    #                     print(f"🎮 Found NVIDIA GPUs: {gpu_ids}")
                
    #         except docker.errors.NotFound:
    #             print(f"❌ Container {container_id} not found in Docker")
    #             return {
    #                 "status": "error",
    #                 "message": f"Container {container_id} not found"
    #             }
    #         except Exception as container_error:
    #             print(f"❌ Error getting container info: {str(container_error)}")
    #             traceback.print_exc()
            
    #         # Step 2: Stop and remove container
    #         print(f"🛑 STEP 2: Stopping container...")
    #         try:
    #             if container.status == "running":
    #                 print(f"   Container is running, stopping...")
    #                 container.stop(timeout=15)
    #                 print(f"   ✅ Container stopped")
    #             else:
    #                 print(f"   Container already stopped (status: {container.status})")
                
    #             print(f"🗑️  STEP 3: Removing container...")
    #             container.remove()
    #             print(f"   ✅ Container removed from Docker")
                
    #         except Exception as docker_error:
    #             print(f"❌ Error during Docker operations: {str(docker_error)}")
    #             traceback.print_exc()
    #             return {
    #                 "status": "error", 
    #                 "message": f"Failed to stop/remove container: {str(docker_error)}"
    #             }
            
    #         # Step 3: Release GPU resources
    #         print(f"🎮 STEP 4: Releasing {len(gpu_ids)} GPU(s)...")
    #         gpu_release_errors = []
            
    #         for i, gpu_id in enumerate(gpu_ids):
    #             try:
    #                 print(f"   Releasing GPU {i+1}/{len(gpu_ids)}: {gpu_id}")
    #                 result = await self.gpu_manager.release_gpu(gpu_id)
    #                 print(f"   ✅ GPU {gpu_id} release result: {result}")
    #             except Exception as gpu_error:
    #                 error_msg = f"Error releasing GPU {gpu_id}: {str(gpu_error)}"
    #                 print(f"   ❌ {error_msg}")
    #                 gpu_release_errors.append(error_msg)
    #                 traceback.print_exc()
            
    #         # Step 4: Update Firebase
    #         print(f"🔥 STEP 5: Updating Firebase status...")
    #         try:
    #             firebase_result = await self.firebase.update_container_status(container_id, "terminated", user_id)
    #             print(f"   ✅ Firebase update result: {firebase_result}")
    #         except Exception as firebase_error:
    #             print(f"   ❌ Firebase update error: {str(firebase_error)}")
    #             traceback.print_exc()
            
    #         # Step 5: Clean up session
    #         print(f"🗄️  STEP 6: Cleaning up session data...")
    #         try:
    #             if hasattr(self, '_session') and self._session:
    #                 session_result = await self._session.cleanup_expired_session(container_id)
    #                 print(f"   ✅ Session cleanup result: {session_result}")
    #             else:
    #                 print(f"   ⚠️  No session manager available")
    #         except Exception as session_error:
    #             print(f"   ❌ Session cleanup error: {str(session_error)}")
    #             traceback.print_exc()
            
    #         # Final verification
    #         print(f"🔍 STEP 7: Final verification...")
    #         try:
    #             # Try to get the container again - should fail
    #             verification_container = self.client.containers.get(container_id)
    #             print(f"⚠️  WARNING: Container still exists after cleanup! Status: {verification_container.status}")
    #         except docker.errors.NotFound:
    #             print(f"   ✅ Verified: Container successfully removed from Docker")
    #         except Exception as verify_error:
    #             print(f"   ❌ Verification error: {str(verify_error)}")
            
    #         print(f"🏁 === DOCKER CLEANUP SERVICE COMPLETE ===\n")
            
    #         # Prepare final result
    #         final_result = {
    #             "status": "success",
    #             "message": "Container cleaned up successfully",
    #             "container_id": container_id,
    #             "user_id": user_id,
    #             "gpus_released": len(gpu_ids),
    #             "gpu_release_errors": gpu_release_errors if gpu_release_errors else None
    #         }
            
    #         if gpu_release_errors:
    #             final_result["warnings"] = f"Some GPU releases failed: {gpu_release_errors}"
            
    #         return final_result
            
    #     except Exception as e:
    #         print(f"💥 CATASTROPHIC ERROR in cleanup_container:")
    #         print(f"❌ Error type: {type(e).__name__}")
    #         print(f"❌ Error message: {str(e)}")
    #         print(f"📍 Full traceback:")
    #         traceback.print_exc()
    #         print(f"🏁 === DOCKER CLEANUP SERVICE FAILED ===\n")
            
    #         return {
    #             "status": "error",
    #             "message": f"Cleanup failed: {str(e)}",
    #             "error_type": type(e).__name__,
    #             "container_id": container_id,
    #             "user_id": user_id
    #         }

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
            "ram_per_gpu":6,
            "cpu_per_gpu":1.5,
            "storage_per_gpu":100
        }

        type_multipliers={
            "jupyter":{"ram":1.0, "cpu":1.0},
            "pytorch":{"ram":1.2, "cpu":1.0},
            "tensorflow":{"ram":1.2, "cpu":1.1},
            "stable-diffusion": {"ram": 1.5, "cpu": 1.0}
        }

        multiplier= type_multipliers.get(container_type, {"ram": 1.0, "cpu": 1.0})

        return{
            "ram_gb":int(base_resources["ram_per_gpu"]*gpu_count*multiplier["ram"]),
            "cpu_count":min(int(base_resources["cpu_per_gpu"]*gpu_count*multiplier["cpu"]), 3),
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

        
                    





          
            
      
           
            
         
           


           
            
           

          

            
            

            

        