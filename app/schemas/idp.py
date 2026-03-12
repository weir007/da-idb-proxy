from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class IDPRequest(BaseModel):
    alias: Optional[str] = None
    displayName: Optional[str] = None
    enabled: bool = True
    trustEmail: bool = False
    # 前端传来的 SAML 技术参数（如 singleSignOnServiceUrl）放在这里
    config: Dict[str, Any] = Field(default_factory=dict)
