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
        key = f"gpu:{gpu_uuid}"
        self.redis.hmset(key, state)



    async def check_gpu_availability(self, requested_gpu:int):

        with self.gpu_lock:
            all_gpus = GPUtil.getGPUs()
            print(f"Found GPUs: {len(all_gpus)}")
            available_gpus = []
            used_gpus = []


            for gpu in all_gpus:
                print(f"Checking GPU: {gpu.uuid}")
                state = await self._get_gpu_state(gpu.uuid)
                print(f"GPU state: {state}")

                if state.get('status')=='in_use':
                    used_gpus.append(gpu.uuid)
                else:
                    available_gpus.append(gpu.uuid)

            print(f"Available GPUs: {len(available_gpus)}")
            print(f"Used GPUs: {len(used_gpus)}")

            if len(available_gpus) < requested_gpu:
                return{
                    "status":"error",
                    "message":"Not enough GPUS are there for your needs,brother.Sorry."
                }
            return available_gpus[:requested_gpu]  #remember we are sending the sliced array
        
    async def allocate_gpu(self, gpu_uuid:str, container_id:str, user_id:str):
        with self.gpu_lock:

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
            await self._set_gpu_state(gpu_uuid, new_state)
            return{
                "status":"success",
                "message":f"GPU {gpu_uuid} allocate successfullly"

            }
        



    async def release_gpu(self, gpu_uuid:str):
        with self.gpu_lock:
            await self._set_gpu_state(gpu_uuid, {'status':"available"})
    

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
            
           
 
       
       
        
        
        

        
            
        

        
        

        
       
       
       


       
        











    
   
