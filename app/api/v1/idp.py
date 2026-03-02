from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.keycloak import kc

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
def create_idp_instance(realm: str, config: dict):
    """创建 IDP 实例"""
    kc.request("POST", f"/realms/{realm}/identity-provider/instances", json=config)
    return {"msg": "SAML Instance created"}


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
