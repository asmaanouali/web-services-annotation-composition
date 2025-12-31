from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Service(BaseModel):
    id: str
    name: str
    filename: str
    endpoint: str
    operations: List[str]
    functionalities: List[str] = Field(default_factory=list)  # payment, booking, search, etc.
    is_annotated: bool = False
    annotations: Optional[Dict[str, Any]] = None
    enriched_wsdl: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
