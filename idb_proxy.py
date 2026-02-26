from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import requests
import time

app = FastAPI(title="Keycloak Business Wrapper API", version="1.0.0")

# --- 配置与工具函数 ---  待替换为从外部配置加载
KEYCLOAK_URL = "http://localhost:8080/auth"  # 替换为你的Keycloak地址，测试用的17.0之前版本，需要加auth
# 建议通过环境变量获取，方便生产部署 KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080").rstrip('/')
ADMIN_REALM = "master"
ADMIN_CLIENT_ID = "admin-cli"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "f**khuawei"


class KeycloakToolError(Exception):
    """自定义 Keycloak 异常，用于携带状态码和原始详情"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


@app.exception_handler(KeycloakToolError)
async def keycloak_exception_handler(request: Request, exc: KeycloakToolError):
    # 这里可以进行错误信息的清洗
    # 例如：Keycloak 返回的 409 可能包含具体的冲突信息，我们有选择地暴露
    error_detail = exc.detail
    try:
        # 尝试解析 Keycloak 返回的 JSON 报错
        import json
        error_json = json.loads(exc.detail)
        error_detail = error_json.get("errorMessage", error_json.get("error", exc.detail))
    except:
        pass

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": exc.status_code,
            "message": f"Keycloak 服务异常: {error_detail}",
            "path": request.url.path
        }
    )


class KeycloakTool:
    def __init__(self):
        self.base_url = KEYCLOAK_URL.rstrip('/')
        self._token = None
        self._token_expires_at = 0
        self.session = requests.Session()
        self.session.trust_env = False

    def get_admin_token(self):
        """获取并缓存 master realm 的管理员 token"""
        # 提前 10 秒预热，防止临界点失效
        if self._token and time.time() < self._token_expires_at - 10:
            return self._token

        url = f"{self.base_url}/realms/{ADMIN_REALM}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": ADMIN_CLIENT_ID,
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
        }

        try:
            response = self.session.post(url, data=data)
            response.raise_for_status()
            res_json = response.json()

            self._token = res_json["access_token"]
            # 记录过期时间 (默认通常是 60s 或 300s)
            self._token_expires_at = time.time() + res_json.get("expires_in", 60)
            return self._token
        except Exception as e:
            print(f"Keycloak Token 获取失败: {e}")
            raise HTTPException(status_code=401, detail="Keycloak Admin Authentication Failed")

    def request(self, method, path, json=None, params=None, headers=None, **kwargs):
        """支持通用的请求，通过 **kwargs 支持 files 等参数"""
        if not headers:
            headers = {"Authorization": f"Bearer {self.get_admin_token()}"}

        url = f"{self.base_url}/admin{path}"

        # 将 json, params, headers 与额外的 kwargs (如 files) 合并发送
        resp = self.session.request(
            method,
            url,
            json=json,
            params=params,
            headers=headers,
            **kwargs
        )

        if resp.status_code >= 400:
            # 打印详细错误方便调试
            print(f"Keycloak API Error [{path}]: {resp.status_code} - {resp.text}")
            raise KeycloakToolError(status_code=resp.status_code, detail=resp.text)
        return resp


client = KeycloakTool()


# --- Schemas (模型定义) ---
class TenantCreate(BaseModel):
    realm: str = Field(..., description="租户唯一标识，对应 Keycloak 的 Realm Name")
    displayName: str = Field(..., description="租户友好显示名称")


class RoleSchema(BaseModel):
    name: str = Field(..., description="角色名称")
    description: Optional[str] = None
    # Pydantic V2 使用 json_schema_extra 来定义示例数据
    attributes: Optional[Dict[str, List[str]]] = Field(
        default=None,
        json_schema_extra={"examples": [{"category": ["business"], "level": ["1"]}]}
    )


class RoleUpdateSchema(BaseModel):
    description: Optional[str] = None
    attributes: Optional[Dict[str, List[str]]] = None


# --- 1. 租户管理 (Tenants) ---

@app.post("/tenants", tags=["Tenants"])
def create_tenant(payload: TenantCreate):
    realm_name = payload.realm
    print(f"DEBUG: 接收到创建租户请求: {payload}")
    # 1) 创建 Realm
    realm_data = {
        "realm": realm_name,
        "displayName": payload.displayName,
        "enabled": True
    }
    client.request("POST", "/realms", json=realm_data)
    print("准备keycloak请求")
    # 2) 创建默认 Client: data-agent (保持不变)
    client_data = {
        "clientId": "data-agent",
        "protocol": "openid-connect",
        "publicClient": False,
        "directAccessGrantsEnabled": True
    }
    client.request("POST", f"/realms/{realm_name}/clients", json=client_data)
    print("转发keycloak请求")
    # 3) 获取 realm-management 客户端的 ID (UUID)
    # Keycloak 所有的管理权限都挂在这个内置 Client 下
    mgmt_clients = client.request("GET", f"/realms/{realm_name}/clients",
                                  params={"clientId": "realm-management"}).json()
    if not mgmt_clients:
        raise HTTPException(status_code=500, detail="Internal Error: realm-management client not found")

    mgmt_client_uuid = mgmt_clients[0]['id']

    # 4) 获取该 Client 下的 'realm-admin' 角色定义
    admin_role_data = client.request("GET", f"/realms/{realm_name}/clients/{mgmt_client_uuid}/roles/realm-admin").json()

    # 5) 创建租户自定义角色 'tenant-admin'
    tenant_admin_role_name = "tenant-admin"
    client.request("POST", f"/realms/{realm_name}/roles",
                   json={"name": tenant_admin_role_name, "description": "Full management access for this realm"})

    # 6) 将 'realm-admin' 权限赋予 'tenant-admin' (设置为复合角色)
    # 这样后续只要给用户分配 tenant-admin，用户就自动拥有了全量管理权限
    client.request(
        "POST",
        f"/realms/{realm_name}/roles/{tenant_admin_role_name}/composites",
        json=[admin_role_data]
    )

    return {
        "msg": f"Tenant {realm_name} created successfully",
        "admin_role": tenant_admin_role_name,
        "assigned_permissions": "realm-management:realm-admin"
    }


@app.get("/tenants", tags=["Tenants"])
def list_tenants():
    realms = client.request("GET", "/realms").json()
    # 屏蔽 master realm
    return [r for r in realms if r['realm'] != 'master']


@app.delete("/tenants/{realm}", tags=["Tenants"])
def delete_tenant(realm: str):
    client.request("DELETE", f"/realms/{realm}")
    return {"msg": f"Tenant {realm} deleted"}


# --- 2. ID Broker 管理 ---

@app.post("/{realm}/idp/saml/import", tags=["IDP"])
async def import_saml_metadata(realm: str, file: UploadFile = File(...)):
    """
    规范化接口：接受真正的文件上传 (Multipart/Form-Data)
    """
    # 1. 读取上传的文件内容
    xml_content = await file.read()

    if len(xml_content) > 1024 * 1024:  # 限制 1MB
        raise HTTPException(status_code=413, detail="元数据文件过大")

    # 2. 构造发往 Keycloak 的数据
    # 保持抓包证实的格式：providerId + file
    data = {"providerId": "saml"}
    files = {
        'file': (file.filename, xml_content, file.content_type)
    }

    # 3. 转发请求
    resp = client.request(
        "POST",
        f"/realms/{realm}/identity-provider/import-config",
        data=data,
        files=files
    )

    return resp.json()


@app.post("/{realm}/idp/saml/instances", tags=["IDP"])
def create_saml_instance(realm: str, config: dict):
    # config 包含 alias, providerId, config 等
    client.request("POST", f"/realms/{realm}/identity-provider/instances", json=config)
    return {"msg": "SAML Instance created"}


# --- 角色管理 (Roles) ---

@app.get("/{realm}/roles", tags=["Roles"])
def list_roles(realm: str):
    """查看角色列表"""
    roles = client.request("GET", f"/realms/{realm}/roles").json()
    # 过滤掉 Keycloak 自动生成的管理角色（可选）
    return [r for r in roles if not r.get('clientRole')]


@app.get("/{realm}/roles/{role_name}", tags=["Roles"])
def get_role_by_name(realm: str, role_name: str):
    """查看指定角色信息 (包含 attributes)"""
    return client.request("GET", f"/realms/{realm}/roles/{role_name}").json()


@app.post("/{realm}/roles", tags=["Roles"])
def create_role(realm: str, role_data: RoleSchema):
    """创建角色，支持设置 attributes"""
    # Keycloak 创建角色时，name 是必填的
    payload = role_data.model_dump(exclude_none=True)
    client.request("POST", f"/realms/{realm}/roles", json=payload)
    return {"msg": f"Role '{role_data.name}' created"}


@app.put("/{realm}/roles/{role_name}", tags=["Roles"])
def update_role(realm: str, role_name: str, update_data: RoleUpdateSchema):
    """更新角色信息 (描述或 attributes)"""
    # 1. 先获取原有数据，防止 PUT 覆盖导致数据丢失
    current_role = client.request("GET", f"/realms/{realm}/roles/{role_name}").json()

    # 2. 合并新旧数据
    update_dict = update_data.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        current_role[key] = value

    # 3. 提交更新
    client.request("PUT", f"/realms/{realm}/roles/{role_name}", json=current_role)
    return {"msg": f"Role '{role_name}' updated"}


@app.delete("/{realm}/roles/{role_name}", tags=["Roles"])
def delete_role(realm: str, role_name: str):
    """删除角色"""
    client.request("DELETE", f"/realms/{realm}/roles/{role_name}")
    return {"msg": f"Role '{role_name}' deleted"}


# --- 4. 群组管理 (Groups) ---

@app.get("/{realm}/groups", tags=["Groups"])
def list_groups(realm: str):
    return client.request("GET", f"/realms/{realm}/groups").json()


@app.get("/{realm}/groups/{group_id}", tags=["Groups"])
def get_group_detail(realm: str, group_id: str):
    group = client.request("GET", f"/realms/{realm}/groups/{group_id}").json()
    members = client.request("GET", f"/realms/{realm}/groups/{group_id}/members").json()
    # 角色信息通常需要单独获取 mappings
    roles = client.request("GET", f"/realms/{realm}/groups/{group_id}/role-mappings").json()
    group['members'] = members
    group['role_mappings'] = roles
    return group


# --- 5. 用户管理 (Users) ---

@app.get("/{realm}/users", tags=["Users"])
def list_users(realm: str):
    return client.request("GET", f"/realms/{realm}/users").json()


@app.get("/{realm}/users/{user_id}/details", tags=["Users"])
def get_user_details(realm: str, user_id: str):
    groups = client.request("GET", f"/realms/{realm}/users/{user_id}/groups").json()
    roles = client.request("GET", f"/realms/{realm}/users/{user_id}/role-mappings").json()
    return {"groups": groups, "roles": roles}


# 导出 OpenAPI JSON 的快捷入口
@app.get("/export-spec", include_in_schema=False)
def export_spec():
    return app.openapi()


# 测试入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090) # 待替换为从外部配置加载
