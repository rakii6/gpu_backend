from fastapi import HTTPException, Request
from services.redis import RedisManager
from typing import Optional
from datetime import datetime
import time

class RateLimiter:

    def __init__(self, redis_client:RedisManager):
        
        self.redis = redis_client.redis
        self.default_rate_limit = 10 #for request
        self.default_time_limit = 60 #window time

    async def check_rate_limit(self,
                               request:Request,
                              ):
        client_ip = request.client.host
        rate_limit_key = f"rate_limit:{client_ip}"


        current_time = int(time.time())

        request_count = self.redis.get(rate_limit_key)
        request_count = int(request_count) if request_count else 0

    

        if request_count >= self.default_rate_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "status":'error',
                    'message':f"Rate limit exceeded, please try again",
                    "limit":self.default_rate_limit,
                    "window":f"{self.default_time_limit} seconds"
                }
            )
        self.redis.incr(rate_limit_key)
        self.redis.expire(rate_limit_key,self.default_time_limit)

        return True