from pydantic import BaseModel
from typing import Optional

class TenantCreate(BaseModel):
    realm: str
    displayName: str

class TenantResponse(BaseModel):
    realm: str
    id: str
    admin_role: str
    admin_user: Optional[str] = None
