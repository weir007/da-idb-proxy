from fastapi import APIRouter
from typing import List
from app.core.keycloak import kc
from app.schemas.roles import RoleCreate, RoleUpdate, RoleResponse
from app.schemas.groups import GroupCreate, GroupUpdate, GroupResponse

router = APIRouter(prefix="/{realm}", tags=["Identity"])


# --- Roles ---
@router.get("/roles", response_model=List[RoleResponse])
def list_roles(realm: str):
    roles = kc.request("GET", f"/realms/{realm}/roles").json()
    # 过滤掉系统内置的 Client Roles，只看 Realm Roles
    return [r for r in roles if not r.get('clientRole')]


@router.post("/roles")
def create_role(realm: str, role: RoleCreate):
    # 转换模型为 JSON，排除空字段
    payload = role.model_dump(exclude_none=True)
    kc.request("POST", f"/realms/{realm}/roles", json=payload)
    return {"msg": f"Role {role.name} created"}


@router.get("/roles/{role_name}", response_model=RoleResponse)
def get_role(realm: str, role_name: str):
    """补全：获取单个角色详情"""
    return kc.request("GET", f"/realms/{realm}/roles/{role_name}").json()


@router.put("/roles/{role_name}")
def update_role(realm: str, role_name: str, role_update: RoleUpdate):
    """补全：更新角色"""
    # 14.0 更新通常需要先拿原有数据进行合并，或者直接 PUT 覆盖
    current = kc.request("GET", f"/realms/{realm}/roles/{role_name}").json()
    update_data = role_update.model_dump(exclude_none=True)
    current.update(update_data)
    kc.request("PUT", f"/realms/{realm}/roles/{role_name}", json=current)
    return {"msg": f"Role {role_name} updated"}


@router.delete("/roles/{role_name}")
def delete_role(realm: str, role_name: str):
    """补全：删除角色"""
    kc.request("DELETE", f"/realms/{realm}/roles/{role_name}")
    return {"msg": f"Role {role_name} deleted"}


# --- Groups ---
@router.get("/groups", response_model=List[GroupResponse])
def list_groups(realm: str):
    """获取所有顶级组及其子树"""
    return kc.request("GET", f"/realms/{realm}/groups").json()


@router.post("/groups", status_code=201)
def create_group(realm: str, group: GroupCreate):
    """创建顶级组"""
    kc.request("POST", f"/realms/{realm}/groups", json=group.model_dump(exclude_none=True))
    return {"msg": f"Group {group.name} created"}


@router.put("/groups/{group_id}")
def update_group(realm: str, group_id: str, group_update: GroupUpdate):
    """更新组信息"""
    # 先获取当前完整对象
    current = kc.request("GET", f"/realms/{realm}/groups/{group_id}").json()
    # 合并更新
    update_data = group_update.model_dump(exclude_none=True)
    current.update(update_data)

    kc.request("PUT", f"/realms/{realm}/groups/{group_id}", json=current)
    return {"msg": f"Group {group_id} updated"}


@router.delete("/groups/{group_id}")
def delete_group(realm: str, group_id: str):
    """删除组"""
    kc.request("DELETE", f"/realms/{realm}/groups/{group_id}")
    return {"msg": f"Group {group_id} deleted"}


# --- Users ---
@router.get("/users")
def list_users(realm: str):
    return kc.request("GET", f"/realms/{realm}/users").json()


@router.get("/users/{user_id}/details")
def get_user_full_context(realm: str, user_id: str):
    """获取用户的完整上下文：所属组 + 拥有的角色"""
    groups = kc.request("GET", f"/realms/{realm}/users/{user_id}/groups").json()
    roles = kc.request("GET", f"/realms/{realm}/users/{user_id}/role-mappings").json()
    return {"groups": groups, "roles": roles}
