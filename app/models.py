from typing import List,Optional
from pydantic import BaseModel
from uuid import uuid4

class Message(BaseModel):
    role: str
    content: str


class Conversation(BaseModel):
    conversation: List[Message]
    lastResponse: str
    interruption: Optional[bool] = False


class Interaction(BaseModel):
    conversation: Conversation
    query: str
    

class Candidate_Schema(BaseModel):
    name: str
    current_ctc: str
    current_company: str
    current_location: str
    work_from_office_home: str
    relocation_bangalore: bool
         
unique_id = str(uuid4())
headers = {"x-key": unique_id}

candidate_info_data = {
    "user_id": unique_id,
    "description": "Candidate information",
    "schema": Candidate_Schema.schema(),
    "instruction": (
        "Extract Candidate information e.g skill,current ctc, current company and location, choice between work from home or office, relocation preference to bangalore"
        
    )
}