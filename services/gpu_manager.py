import GPUtil 
from typing import List, Dict
from threading import Lock
class GPUManager:
    def __init__(self):
        self.gpu_lock = Lock()

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
    async def check_gpu_availability(self,requested_gpu:int):
        
       """Check Total GPU Count: Use GPUtil.getGPUs() to get all GPUs.
             1) Validate required_gpu:
               2)  If required_gpu > 8, immediately return "No."
               3)  If required_gpu is less than or equal to 8, check availability.
                4)  Find Free GPUs:
                5)  Use GPUtil.getAvailable() to get the free GPUs based on their memory and utilization.
                6)  Compare Availability:
                If there aren’t enough free GPUs to meet the requirement, return "No."
                Otherwise, return the UUIDs of the free GPUs
       """
       with self.gpu_lock:
        try:
            all_gpus = GPUtil.getGPUs()
            total_gpus = len(all_gpus)
            if requested_gpu> total_gpus:
                return{
                "status":"Not allowed",
                "message":"Your request is over the limit"
            }
            free_gpus = GPUtil.getAvailable(order = "memory",limit=requested_gpu)

            if len(free_gpus)<requested_gpu:
                return{
                "status":"no",
                "message": f"Only {len(free_gpus)} GPUs are free"
            }

            gpu_uuids = [all_gpus[gpu_id].uuid for gpu_id in free_gpus]
            return gpu_uuids #this gives me a list, remember that 
        
        except Exception as e:
           return{
               "status":"error from check gpu method, ",
               "message":str(e)
           }
            
           
 
       
       
        
        
        

        
            
        

        
        

        
       
       
       


       
        











    
   
