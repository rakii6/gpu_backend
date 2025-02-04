import GPUtil 
from typing import List, Dict
from threading import Lock
from services.redis import RedisManager
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

       
    @staticmethod
    def get_gpu_stats()-> List[Dict]:

        try:
            gpus = GPUtil.getGPUs()
            gpu_stats=[]

            for gpu in gpus:
                stats={
                    'id':gpu.id,
                    'name':gpu.name,
                    'load':round(gpu.load*100,2),
                    'memory':{
                        'used':gpu.memoryUsed,
                        'total':gpu.memoryTotal,
                        'free':gpu.memoryTotal - gpu.memoryUsed,
                        'percent_used':round((gpu.memoryUsed/gpu.memoryTotal)*100, 2)

                    },
                    'temperature':gpu.temperature,
                    'uuid':gpu.uuid
                }
                gpu_stats.append(stats)
                
                
            return gpu_stats
        except  Exception as e:
            return {
                'message':"error getting Gpu stats",
                'error':str(e)
            }
    async def check_gpu_availability(self, requested_gpu: int):
        print(f"Checking availability for {requested_gpu} GPUs")
    
        with self.gpu_lock:
            try:
            # Get physical GPUs
                all_gpus = GPUtil.getGPUs()
                print(f"Total physical GPUs found: {len(all_gpus)}")
            
                if requested_gpu > len(all_gpus):
                    return {
                        "status": "Not allowed",
                        "message": f"Request exceeds limit. Max GPUs: {len(all_gpus)}"
                    }

            # Check availability in Redis
                available_gpus = []
                for gpu in all_gpus:
                    try:
                        # Changed self.redis_manager.redis to self.redis
                        gpu_status = self.redis.hget(f"gpu:{gpu.uuid}", "status") # we get gpu from redis with key and statyus
                        if gpu_status is None or gpu_status.decode('utf-8') == 'available':
                            available_gpus.append(gpu.uuid) #we store the gpus with availabe stauts or none
                    except Exception as redis_error:
                        print(f"Error checking GPU {gpu.uuid}: {str(redis_error)}")
                        continue
                    
            
                if len(available_gpus) < requested_gpu: #here we check if the lenght is okay or not
                    return {
                        "status": "no",
                        "message": f"Only {len(available_gpus)} GPUs are free"
                    }

                selected_gpus = available_gpus[:requested_gpu] #slice the ids

                for gpu_id in selected_gpus:
                    self.redis.hset(f"gpu:{gpu_id}", "status", "in_use") #take those selected ids and change status
                print(f"Selected GPUs: {selected_gpus}")
                return selected_gpus

            except Exception as e:
                print(f"Error in GPU check: {str(e)}")
                return {
                "status": "error",
                "message": str(e)
            }
        

# Clean Error Recovery method()
# What happens if a GPU becomes unavailable mid-check?
# Add retries for transient failures
            
           
 
       
       
        
        
        

        
            
        

        
        

        
       
       
       


       
        











    
   
