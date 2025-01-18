from pydantic import BaseModel
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
    subdomain:str