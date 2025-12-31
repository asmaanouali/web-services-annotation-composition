from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class CompositionStep(BaseModel):
    step_number: int
    source_service: str
    needed_function: str
    available_services: List[Dict[str, Any]]
    selected_service: Optional[str] = None
    selected_operation: Optional[str] = None
    score: Optional[float] = None
    
class CompositionResult(BaseModel):
    step: int
    source_service: str
    needed_function: str
    selected_service: str
    selected_operation: str
    method: str  # 'classic' or 'intelligent'
    score: Optional[float] = None
    execution_time: int
    annotations_used: Optional[Dict[str, Any]] = None
