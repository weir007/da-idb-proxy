from pydantic import BaseModel

class TenantCreate(BaseModel):
    realm: str
    displayName: str

class TenantResponse(BaseModel):
    realm: str
    id: str
    admin_role: str
