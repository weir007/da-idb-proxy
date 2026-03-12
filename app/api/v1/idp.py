from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.core.keycloak import kc
from app.api.v1.common import skip_master_realm
from app.schemas.idp import IDPRequest

import os

router = APIRouter(prefix="/{realm}/idp", tags=["IDP"], dependencies=[Depends(skip_master_realm)])


@router.post("/saml/import")
async def import_saml_metadata(realm: str, file: UploadFile = File(...)):
    """从 XML 文件导入 IDP 配置"""
    xml_content = await file.read()

    # 构造 Keycloak 要求的 Form-Data 格式
    files = {
        'file': (file.filename, xml_content, file.content_type)
    }
    data = {"providerId": "saml"}

    # 转发至 Keycloak 导入接口
    resp = kc.request(
        "POST",
        f"/realms/{realm}/identity-provider/import-config",
        data=data,
        files=files
    )
    return resp.json()


def _validate_saml_config(config: dict):
    """
    模拟 Keycloak 界面校验逻辑：确保 SAML 核心配置不为空
    防止 API 创建/更新出“Add/Save 按钮灰色”的无效实例
    """
    # 26.5 界面最核心的三个必填项
    required_fields = {
        "singleSignOnServiceUrl": "SSO Service URL"
        # "entityId": "Service Provider Entity ID",
    }

    missing = [desc for field, desc in required_fields.items() if not config.get(field)]

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required SAML configuration: {', '.join(missing)}"
        )


@router.post("/saml/instances", status_code=201)
def create_idp_instance(realm: str, payload: IDPRequest):
    """创建 IDP 实例：限制单实例，强制注入环境变量 Alias"""

    # 1. 限制一个 Realm 仅一个 (原有逻辑)
    existing = kc.request("GET", f"/realms/{realm}/identity-provider/instances").json()
    if len(existing) > 0:
        raise HTTPException(status_code=400, detail="Realm already has an IDP instance.")

    # 2. 核心校验 (解决界面按钮置灰问题)
    _validate_saml_config(payload.config)

    # 3. 获取环境变量别名 (原有逻辑)
    alias = os.getenv("DEFAULT_IDP_ALIAS", "da-saml-idp")

    # 4. 构造完整 Payload
    # 强制注入 providerId 和 alias
    idp_data = {
        "alias": alias,
        "displayName": payload.displayName or alias,
        "providerId": "saml",
        "enabled": payload.enabled,
        "trustEmail": payload.trustEmail,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": payload.config
    }

    # 5. 发送请求
    res = kc.request("POST", f"/realms/{realm}/identity-provider/instances", json=idp_data)
    return {"msg": "Created", "alias": alias}


@router.put("/saml/instances")
def update_idp_instance(realm: str, payload: IDPRequest):
    """更新 IDP 实例：先 GET 再合并 PUT"""
    alias = os.getenv("DEFAULT_IDP_ALIAS", "da-saml-idp")

    # 1. 先获取旧配置 (原有逻辑：探测是否存在并获取完整对象)
    check = kc.request("GET", f"/realms/{realm}/identity-provider/instances/{alias}")
    if check.status_code == 404:
        raise HTTPException(status_code=404, detail=f"IDP {alias} not found.")

    current_full_data = check.json()

    # 2. 合并配置
    # 更新外层
    current_full_data["enabled"] = payload.enabled
    current_full_data["trustEmail"] = payload.trustEmail
    if payload.displayName:
        current_full_data["displayName"] = payload.displayName

    # 更新内层 config (合并而不是替换，防止丢失原有证书等信息)
    current_full_data["config"].update(payload.config)

    # 3. 校验合并后的结果 (解决界面修改后无法保存问题)
    _validate_saml_config(current_full_data["config"])

    # 4. 强制 Alias 不可变
    current_full_data["alias"] = alias

    # 5. 发送更新 (Keycloak 26.5 标准 PUT)
    kc.request("PUT", f"/realms/{realm}/identity-provider/instances/{alias}", json=current_full_data)

    return {"msg": "Updated", "alias": alias}


@router.get("/saml/instances")
def list_idp_instances(realm: str):
    """获取该 Realm 下所有的 IDP 实例列表"""
    return kc.request("GET", f"/realms/{realm}/identity-provider/instances").json()


@router.delete("/saml/instances/{alias}", status_code=status.HTTP_204_NO_CONTENT)
def delete_idp_instance(realm: str, alias: str):
    """
    删除 SAML 2.0 IDP 实例
    :param realm: 租户名称
    :param alias: IDP 的唯一别名 (比如 'saml-idp-01')
    """
    # Keycloak 14.0 标准路径: /auth/admin/realms/{realm}/identity-provider/instances/{alias}
    resp = kc.request("DELETE", f"/realms/{realm}/identity-provider/instances/{alias}")

    # 如果别名不存在，14.0 可能会报 404，我们通过 kc.request 内部处理或这里补充逻辑
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"IDP instance '{alias}' not found in realm '{realm}'")

    return None  # 204 No Content 不需要返回 body
