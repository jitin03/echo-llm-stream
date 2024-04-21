from typing import List,Optional
from pydantic import BaseModel


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
    
