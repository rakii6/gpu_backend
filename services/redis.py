from dotenv import load_dotenv
import os
import redis

load_dotenv()
redis_love=os.getenv("REDIS_LOVER")



class RedisManager:
    def __init__(self):
        try:
            self.redis= redis.Redis(
                host='localhost',
                port=6379,
                password=redis_love
            )
        except Exception as e:
            return{
                "status":"error from Redis Init seciton",
                "message":str(e)
            }
    
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

    

    