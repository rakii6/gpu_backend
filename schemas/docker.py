from pydantic import BaseModel, field_validator
from typing import List, Optional

class ContainerInfo(BaseModel):
    id:str
    name:str
    status: str

class ContainerResponse(BaseModel):
    status:str
    container_id:Optional[str]=None
    message:Optional[str]=None

class ContainerRequest(BaseModel):
    user_id:str
    container_type:str
    subdomain:str     #this subdomina we are creating ourselves, need to be created by us
    gpu_count: int=1
    duration: int=1 #needs changing

    @field_validator("duration")
    @classmethod
    def duration_checker(cls, duration):
        if duration < 1:
            raise ValueError("duration must be more than 1 hour")
        if duration > 168:
            raise ValueError("You cannot use the GPUs for more than a week")
        return duration
