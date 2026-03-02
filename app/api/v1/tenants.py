from typing import List
from fastapi import APIRouter, status
from app.core.keycloak import kc
from app.schemas.realm import TenantCreate, TenantResponse


router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("", response_model=List[dict])
def list_tenants():
    """获取所有租户 (GET /api/v1/tenants)"""
    realms = kc.request("GET", "/realms").json()
    # 过滤 master
    return [r for r in realms if r['realm'] != 'master']


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TenantResponse)
def create_tenant(payload: TenantCreate):
    realm = payload.realm

    # 1. 创建 Realm
    kc.request("POST", "/realms", json={
        "realm": realm, "displayName": payload.displayName, "enabled": True
    })

    # 2. 创建默认 Client (data-agent)
    kc.request("POST", f"/realms/{realm}/clients", json={
        "clientId": "data-agent",
        "publicClient": True,
        "standardFlowEnabled": True,
        "redirectUris": ["*"],
        "webOrigins": ["*"]
    })

    # 3. 编排权限：获取 realm-management 并筛选出那 5 个核心 Role
    mgmt_clients = kc.request("GET", f"/realms/{realm}/clients", params={"clientId": "realm-management"}).json()
    mgmt_uuid = mgmt_clients[0]['id']

    all_roles = kc.request("GET", f"/realms/{realm}/clients/{mgmt_uuid}/roles").json()
    # 你之前提到的 5 个核心管理权限
    target_names = ["manage-realm", "manage-identity-providers", "manage-users", "view-users", "query-users"]
    selected_roles = [r for r in all_roles if r['name'] in target_names]

    # 4. 创建 tenant-admin 角色并绑定复合权限
    admin_role_name = "tenant-admin"
    kc.request("POST", f"/realms/{realm}/roles", json={"name": admin_role_name})
    kc.request("POST", f"/realms/{realm}/roles/{admin_role_name}/composites", json=selected_roles)

    return {
        "realm": realm,
        "id": realm,
        "admin_role": admin_role_name
    }


@router.delete("/{realm_name}")
def delete_tenant(realm_name: str):
    """删除租户 (DELETE /api/v1/tenants/{realm_name})"""
    kc.request("DELETE", f"/realms/{realm_name}")
    return {"msg": f"Tenant {realm_name} deleted"}
