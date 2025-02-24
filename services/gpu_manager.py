import GPUtil 
from typing import List, Dict
from threading import Lock
from services.redis import RedisManager
from datetime import datetime
class GPUManager:

    is_initialized = False
    shared_lock = None
   

    def __init__(self, redis_manager: RedisManager):
        """
        Initialize GPU Manager with a Redis instance
        Args:
            redis_manager: Instance of RedisManager
        """

        if not GPUManager.is_initialized:
            print("initiazling gpu mangaer now")
            GPUManager.shared_lock = Lock()
            GPUManager.is_initialized = True
            print("GPU Manager initialized")
        self.redis = redis_manager.redis
        self.gpu_lock = GPUManager.shared_lock

    async def _get_gpu_state(self, gpu_uuid:str)->Dict:
        key = f"gpu:{gpu_uuid}"
        state = self.redis.hgetall(key)

        return {k.decode('utf-8'):v.decode('utf-8') for k,v in state.items()} if state else{} #ternary opertiion
    

    async def _set_gpu_state(self, gpu_uuid: str, state:dict):
        all_gpus = GPUtil.getGPUs()
        if gpu_uuid not in [gpu.uuid for gpu in all_gpus]:
            print(f"Warning: Attempting to set state for unknown GPU: {gpu_uuid}")
            return {}
        
        key = f"gpu:{gpu_uuid}"
        self.redis.delete(key)

        if state:
            self.redis.hset(key, mapping=state)
        print(f"just set the new state for {key}")
        return state




    async def check_gpu_availability(self, requested_gpu:int):

        with self.gpu_lock:
            all_gpus = GPUtil.getGPUs()
            
            available_gpus = []
            used_gpus = []


            for gpu in all_gpus:
                state = await self._get_gpu_state(gpu.uuid)

                if state.get('status')=='in_use':
                    used_gpus.append(gpu.uuid)
                else:
                    available_gpus.append(gpu.uuid)


            if len(available_gpus) < requested_gpu:
                return{
                    "status":"error",
                    "message":"Not enough GPUS are there for your needs,brother.Sorry."
                }
            return available_gpus[:requested_gpu]  #remember we are sending the sliced array
        
    async def allocate_gpu(self, gpu_uuid:str, container_id:str, user_id:str):
        with self.gpu_lock:
            print(f"attempting tto allocate gpu{gpu_uuid}")
            current_state =  await self._get_gpu_state(gpu_uuid)
            if current_state.get('status')=='in_use':
                return{
                    "error":"error",
                    "message":f"gpu{gpu_uuid} is  already in use"
                }
            
            new_state = {
                'status': 'in_use',
                'container_id': container_id,
                'user_id': user_id,
                'allocated_at': datetime.now().isoformat()
            }
            print(f"Now Setting new state for GPU {gpu_uuid}: {new_state}")
            updated_state=await self._set_gpu_state(gpu_uuid, new_state)
            print(f"Verified state after update: {updated_state}")
            return{
                "status":"success",
                "message":f"GPU {gpu_uuid} allocate successfullly"

            }
        



    async def release_gpu(self, gpu_uuid:str):
        with self.gpu_lock:
             new_state = {
            'status': 'available',
            'container_id': '',
            'user_id': '',
            'allocated_at': ''
        }
        await self._set_gpu_state(gpu_uuid, new_state)
        return{
            "status":"success",
            "message":f"GPU{gpu_uuid} released"
        }

    async def get_container_gpus(self, container_id:str)-> List:
        """GET alll the  gpus to a container"""

        all_gpus = GPUtil.getGPUs()
        container_gpus = []

        for gpu  in all_gpus:
            state = await self._get_gpu_state(gpu.uuid)
            if state.get('container_id') == container_id:
                container_gpus.append(gpu.uuid)
        return container_gpus

# Clean Error Recovery method()
# What happens if a GPU becomes unavailable mid-check?
# Add retries for transient failures
            
           
 
       
       
        
        
        

        
            
        

        
        

        
       
       
       


       
        











    
   
