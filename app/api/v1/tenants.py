from typing import List
from fastapi import APIRouter, status, HTTPException
from fastapi.params import Depends

from app.core.keycloak import kc
from app.schemas.realm import TenantCreate, TenantResponse
from app.api.v1.common import skip_master_realm
import os


router = APIRouter(prefix="/tenants", tags=["Tenants"])


# 获取受保护的 Master Realm 名称，默认为 "master"
PROTECTED_REALM = os.getenv("KC_REALM", "master")


@router.get("", response_model=List[dict])
def list_tenants():
    """获取所有租户，自动过滤掉 master"""
    realms = kc.request("GET", "/realms").json()
    return [r for r in realms if r['realm'].lower() != PROTECTED_REALM.lower()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TenantResponse,
             dependencies=[Depends(skip_master_realm)])
def create_tenant(payload: TenantCreate):
    # 拦截尝试创建或覆盖 master 的行为
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

    # 3. 编排权限
    mgmt_clients = kc.request("GET", f"/realms/{realm}/clients", params={"clientId": "realm-management"}).json()
    mgmt_uuid = mgmt_clients[0]['id']

    all_roles = kc.request("GET", f"/realms/{realm}/clients/{mgmt_uuid}/roles").json()
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


@router.delete("/{realm_name}", dependencies=[Depends(skip_master_realm)])
def delete_tenant(realm_name: str):
    kc.request("DELETE", f"/realms/{realm_name}")
    return {"msg": f"Tenant {realm_name} deleted successfully"}
