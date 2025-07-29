from pydantic import BaseModel, field_validator, Field
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
    user_id:Optional[str] = None #I made this optional since the middle ware will alawys provide it.
    container_type:str
    subdomain:str     #this subdomina we are creating ourselves, need to be created by us
    gpu_count: int=1
    duration: int=1 #needs changing int=1
   

    @field_validator("duration")
    @classmethod
    def duration_checker(cls, duration):
        if duration < 1:
            raise ValueError("duration must be more than 1 hour")
        if duration > 168:
            raise ValueError("You cannot use the GPUs for more than a week")
        return duration

class PaymentRequest(BaseModel):
    amount: float  # In rupees
    currency: str 
    user_id:str
    container_request:str

class SupportRequest(BaseModel):
    user_id: str = Field(..., alias="userId")  # Handle both userId and user_id
    support_code: str = Field(..., alias="supportCode")
    issue: str = Field(..., alias="description")  # Your frontend sends 'description'
    issue_type: str = Field(..., alias="issueType")
    user_email: str = Field(None, alias="userEmail")
    user_agent: str = Field(None, alias="userAgent")
    timestamp: str = Field(None)
    source: str = Field(None)

