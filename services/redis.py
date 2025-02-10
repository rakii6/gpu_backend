from dotenv import load_dotenv
import os
import redis
from datetime import datetime
import time
import json
import GPUtil
import threading
load_dotenv()
redis_love=os.getenv("REDIS_LOVER")



class RedisManager:

    is_connected =False
    redis_client =None

    def __init__(self):
        if not RedisManager.is_connected:
            try:
                print("Connecting to Redis for the first time...")
                RedisManager.redis_client= redis.Redis(
                host='localhost',
                port=6379,
                password=redis_love
                )
                RedisManager.is_connected = True
                print("Redis connection established")
                
            except Exception as e:
                # return{
                # "status":"error from Redis Init seciton",
                # "message":str(e)}
                print(f"Failed to connect to Redis: {e}")
                raise
        self.redis = RedisManager.redis_client
        self.gpu_lock = threading.Lock()

        
    
    def redis_overlord(self):# Function to update/note/check GPU status in Redis daily
            try:
                print("starting detections ...........")

                GPUS=GPUtil.getGPUs()
                print(f"Number of GPUs detected: {len(GPUS)}")
                stored_count = 0

                if not GPUS:
                    print("warning: no GPus detected")
                    return

                for gpu in GPUS:
                    try:

                        gpu_id = gpu.uuid
                        print(type(gpu_id))
                        # print(f"Processing GPU: {gpu_id}")

                        gpu_status ={

                            "memoryFree": str(gpu.memoryFree),
                            "memoryTotal": str(gpu.memoryTotal),
                            "memoryUsed": str(gpu.memoryUsed),
                            "status": "available" if gpu.memoryFree > 1000 else "in_use"  # Simple rule
                        }
                        for field, value in gpu_status.items():
                            self.redis.hset(f"gpu:{gpu_id}", field, value)
                    
                        self.redis.expire(f"gpu:{gpu_id}",86400)
                        stored_count += 1
                        print(f"Successfully stored GPU {gpu.id} with key {gpu_id}")
                    except Exception as e:
                        print(f"Error storing GPU {gpu.id}: {str(e)}")



                
                print(f"Stored {stored_count} out of {len(GPUS)} GPUs")
           
            except Exception as e:
                print(f"Error in redis_overlord: {str(e)}")
              

    
    def run_periodic_update(self):#function to run redis overlord very 10mins
        while True:
            self.redis_overlord()
            # self.test_gpu_detection()
            time.sleep(600)
    def start_gpu_status_update(self):# Background thread to start the periodic update
        status_update_thread = threading.Thread(target=self.run_periodic_update)
        status_update_thread.daemon = True #background
        status_update_thread.start()
                


    async def test_connection(self):
        try:
            self.redis.set('test_key', 'hello GPU monitoring')
            value = self.redis.get('test_key')
            return{
                "status":"success",
                "message":value.decode('utf-8')
            }
        except redis.ConnectionError as e:
            return{
                "status":"error redis from redis.connection block",
                "message":str(e)
                
            }
        except Exception as e:
            return{
                "status":"error from the test connection method block",
                "message":str(e)
            }
   

    async def mark_extracted_gpu(self, gpu_uid:str, container_id:str, user_id:str, ttl:int=3600): 
        """ttl needs to be as per user input, please remember""" 
        try:
            key = f"gpu:{gpu_uid}"
            data = {
                'status':"in_use",
                'allocated_at': datetime.now().isoformat(),
                'docker_container_id':container_id,
                'user_id':user_id,
            }
            data_str = json.dumps(data)
            
            self.redis.hmset(key, data)
            self.redis.expire(key, ttl)

            return{
                "status":"success",
                "message":"data updated in redis db",
                "ttl":f"self destrcuct in {ttl} seconds"
            }
        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }




    async def store_gpu_metrics(self, gpu_uid:str, metrics:dict, ttl:int= 3600):
        
        """Here we will get the status of the gpu allocation"""
       
        try:
            redis_key = f"entry:{gpu_uid}"
            metric_key = f"metrics:{gpu_uid}"

            self.redis.hmset(redis_key, metrics)

            if ttl>0:
                self.redis.expire(redis_key, ttl)
            
            self.redis.hincrby(metric_key, "update count", 1)

            return{
                "status":"success",
                "message":f"metrics for {gpu_uid} has  been stored.",
                "ttl":f"time to destruct in {ttl}seconds"
            }
        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }

    # async def allocate_gpu(self, gpu_id:int, container_id:str):
    #     """here we will check if a gpu is allocated to a 
    #     container or not, but we need to get the id
    #     of container when being created to allocate here in the """
        
    #     try:

    

    