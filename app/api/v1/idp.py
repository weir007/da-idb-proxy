from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.keycloak import kc

import os

router = APIRouter(prefix="/{realm}/idp", tags=["IDP"])


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


@router.post("/saml/instances")
def create_idp_instance(realm: str, user_config: dict):
    """
    创建 IDP 实例：强制注入 Alias 和 ProviderID
    """
    # 1. 检查 Realm 下是否已有 IDP
    existing = kc.request("GET", f"/realms/{realm}/identity-provider/instances").json()
    if len(existing) > 0:
        raise HTTPException(status_code=400, detail="Realm already has an IDP instance.")

    alias = os.getenv("DEFAULT_IDP_ALIAS", "da-saml-idp")

    # 2. 构造/修正配置字典
    # 就算 user_config 是空的 {}，下面这些赋值也会生效
    payload = user_config.copy()

    # 强制外层属性
    payload["alias"] = alias
    payload["providerId"] = "saml"
    payload["enabled"] = payload.get("enabled", True)

    # 关键：SAML 的核心参数其实在内层的 "config" 字段里
    # 如果用户没传内层 config，我们需要初始化它，否则 Keycloak 会报 400
    if "config" not in payload:
        payload["config"] = {}

    # 3. 发送请求
    res = kc.request("POST", f"/realms/{realm}/identity-provider/instances", json=payload)

    if res.status_code != 201:
        raise HTTPException(status_code=res.status_code, detail=res.text)

    return {"msg": "Created", "alias": alias}


@router.put("/saml/instances")
def update_idp_instance(realm: str, user_config: dict):
    """
    更新 IDP 实例：使用环境变量 Alias 定位
    """
    alias = os.getenv("DEFAULT_IDP_ALIAS", "da-saml-idp")

    # 1. 先探测是否存在
    check = kc.request("GET", f"/realms/{realm}/identity-provider/instances/{alias}")
    if check.status_code == 404:
        raise HTTPException(status_code=404, detail=f"IDP {alias} not found.")

    # 2. 合并配置
    # 注意：Keycloak 的 PUT 通常是全量更新。
    # 建议先拿到旧配置，再用新配置覆盖，防止丢失未传的字段。
    current_config = check.json()
    current_config.update(user_config)  # 用传入的覆盖旧的

    # 强制修正核心字段不可变
    current_config["alias"] = alias
    current_config["internalId"] = current_config.get("internalId")  # 必须带上这个 ID

    # 3. 发送更新
    res = kc.request("PUT", f"/realms/{realm}/identity-provider/instances/{alias}", json=current_config)

    if res.status_code not in [200, 204]:
        raise HTTPException(status_code=res.status_code, detail=res.text)

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
