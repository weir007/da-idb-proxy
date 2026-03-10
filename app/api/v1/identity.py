from fastapi import APIRouter, Depends
from typing import List
from app.core.keycloak import kc
from app.schemas.roles import RoleCreate, RoleUpdate, RoleResponse
from app.schemas.groups import GroupCreate, GroupUpdate, GroupResponse, GroupDetailResponse
from app.api.v1.common import skip_master_realm


router = APIRouter(prefix="/{realm}", tags=["Identity"], dependencies=[Depends(skip_master_realm)])


def is_internal_role(role_name: str) -> bool:
    """
    判断是否为 Keycloak 内置角色
    1. 过滤默认生成的 default-roles-{realm}
    2. 过滤常见的内置管理角色名
    """
    internal_prefixes = ["default-roles-", "offline_access", "uma_authorization"]
    # 如果角色名以这些开头，或者是常见的内置角色，则拦截
    return any(role_name.startswith(p) for p in internal_prefixes)


# --- Roles ---
@router.get("/roles", response_model=List[RoleResponse])
def list_roles(realm: str):
    roles = kc.request("GET", f"/realms/{realm}/roles").json()
    # 过滤掉系统内置的 Client Roles，只看 Realm Roles
    return [
        r for r in roles
        if not r.get('clientRole') and not is_internal_role(r.get('name', ''))
    ]


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


@router.get("/groups/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(realm: str, group_id: str):
    """获取 Group 详情：基础 + 成员(仅名) + 角色(过滤内置)"""

    # 1. 基础信息
    group_base = kc.request("GET", f"/realms/{realm}/groups/{group_id}").json()

    # 2. 获取成员并清洗字段
    raw_members = kc.request("GET", f"/realms/{realm}/groups/{group_id}/members").json()
    # 显式提取，确保只给前端 id 和 username
    members = [{"id": m["id"], "username": m["username"]} for m in raw_members]

    # 3. 获取角色映射并过滤
    role_mappings = kc.request("GET", f"/realms/{realm}/groups/{group_id}/role-mappings").json()
    # Keycloak 返回的 realmMappings 结构通常是 [{'id': '...', 'name': '...'}, ...]
    realm_roles = role_mappings.get("realmMappings", [])

    # 过滤掉内置角色 (如 default-roles-xxx)
    filtered_roles = [r for r in realm_roles if not is_internal_role(r['name'])]

    # 4. 组装返回，FastAPI 会自动根据 RoleResponse 过滤 roles 里的多余字段
    return {
        "id": group_base["id"],
        "name": group_base["name"],
        "members": members,
        "roles": filtered_roles
    }


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
    """
    获取用户的完整上下文：所属组 + 拥有的角色 (已过滤内置角色)
    注意：此接口已通过 router 级别的 skip_master_realm 依赖自动拦截 master
    """
    # 1. 获取用户所属的组
    groups = kc.request("GET", f"/realms/{realm}/users/{user_id}/groups").json()

    # 2. 获取用户的角色映射
    # Keycloak 返回结构: {"realmMappings": [...], "clientMappings": {...}}
    role_mappings = kc.request("GET", f"/realms/{realm}/users/{user_id}/role-mappings").json()

    # 3. 提取 Realm 级别角色并过滤内置角色
    realm_roles = role_mappings.get("realmMappings", [])
    filtered_roles = [
        r for r in realm_roles
        if not is_internal_role(r.get("name", ""))
    ]

    # 4. (可选) 如果你也需要过滤 Client 级别的内置角色，可以在这里处理 clientMappings
    # 目前根据你的需求，我们重点拦截 Realm 级别的内置角色

    return {
        "groups": groups,
        "roles": filtered_roles
    }
