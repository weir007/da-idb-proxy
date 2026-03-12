from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from app.schemas.roles import RoleResponse


class GroupMember(BaseModel):
    id: str
    username: str

class GroupDetailResponse(BaseModel):
    id: str
    name: str
    # 聚合后的字段
    members: List[GroupMember] = []
    roles: List[RoleResponse] = []

    class Config:
        from_attributes = True


class GroupBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., examples=["Engineering_Dept"])
    path: Optional[str] = Field(None, description="组的全路径，例如 /Parent/Child")
    attributes: Optional[Dict[str, List[str]]] = Field(None, description="组的扩展属性")


class GroupCreate(GroupBase):
    users: Optional[List[str]] = []  # 用户 ID 列表
    roles: Optional[List[str]] = []  # 角色名称列表


class GroupUpdate(GroupCreate): # 继承 Create 以获得相同的字段
    name: Optional[str] = None


class GroupResponse(GroupBase):
    """查询返回的模型，包含递归的子组"""
    id: str = Field(..., description="Keycloak 自动生成的 UUID")
    # 关键点：递归引用自身，处理嵌套的 subGroups
    subGroups: List["GroupResponse"] = Field(default_factory=list)


# Pydantic V2 必须调用此方法来解析循环引用
GroupResponse.model_rebuild()
