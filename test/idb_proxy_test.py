import requests
import json
import uuid
import io


# 配置信息
BASE_URL = "http://127.0.0.1:8090"
TEST_REALM = f"realm-{uuid.uuid4().hex[:6]}"  # 生成随机名避免冲突
SAML_ALIAS = "saml-idp-test"


class KeycloakWrapperTester:
    def __init__(self):
        self.session = requests.Session()
        # 核心：禁用系统代理环境变量，解决公司内网拦截问题
        self.session.trust_env = False
        self.base_url = BASE_URL

    def log(self, step, resp):
        print(f"\n>> Step: {step}")
        print(f"   Status: {resp.status_code}")
        try:
            print(f"   Data: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        except:
            print(f"   Raw: {resp.text[:100]}")

    # --- 1. 租户管理场景 ---
    def test_tenant_management(self):
        print("\n=== [场景 1: 租户管理] ===")
        # 创建
        payload = {"realm": TEST_REALM, "displayName": "自动化测试租户"}
        res = self.session.post(f"{self.base_url}/tenants", json=payload)
        self.log("创建租户", res)

        # 列表
        res = self.session.get(f"{self.base_url}/tenants")
        self.log("查看租户列表", res)

    # --- 2. 角色管理场景 (带 Attributes) ---
    def test_role_management(self):
        print("\n=== [场景 2: 角色管理] ===")
        role_name = "test_business_role"

        # 创建角色
        payload = {
            "name": role_name,
            "description": "测试用角色说明",
            "attributes": {"level": ["gold"], "region": ["asia"]}
        }
        res = self.session.post(f"{self.base_url}/{TEST_REALM}/roles", json=payload)
        self.log("添加角色", res)

        # 获取角色详情
        res = self.session.get(f"{self.base_url}/{TEST_REALM}/roles/{role_name}")
        self.log("查看指定角色信息", res)

        # 更新角色属性
        update_payload = {
            "attributes": {"level": ["platinum"], "region": ["asia"], "tag": ["new"]}
        }
        res = self.session.put(f"{self.base_url}/{TEST_REALM}/roles/{role_name}", json=update_payload)
        self.log("更新角色属性", res)

        # 删除角色
        res = self.session.delete(f"{self.base_url}/{TEST_REALM}/roles/{role_name}")
        self.log("删除角色", res)

    # --- 3. IDP 管理场景 ---
    def test_idp_management(self):
        print("\n=== [场景 3: IDP 管理] ===")
        # 1. 模拟导入 SAML XML
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
                <EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="http://mock-idp">
                    <IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
                        <SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://mock-idp/sso"/>
                    </IDPSSODescriptor>
                </EntityDescriptor>"""

        # 构造文件对象进行上传
        files = {
            'file': ('metadata.xml', io.BytesIO(xml_content.encode('utf-8')), 'text/xml')
        }
        res = self.session.post(f"{self.base_url}/{TEST_REALM}/idp/saml/import", files=files)
        self.log("导入SAML配置", res)

        if res.status_code == 200:
            parsed_config = res.json()
            # 2. 创建 IDP Instance
            idp_payload = {
                "alias": SAML_ALIAS,
                "providerId": "saml",
                "enabled": True,
                "config": parsed_config
            }
            res = self.session.post(f"{self.base_url}/{TEST_REALM}/idp/saml/instances", json=idp_payload)
            self.log("创建SAML实例", res)

    # --- 4. 群组与用户查询场景 ---
    def test_query_operations(self):
        print("\n=== [场景 4: 群组与用户查询] ===")
        # 查看群组列表
        res = self.session.get(f"{self.base_url}/{TEST_REALM}/groups")
        self.log("查看群组列表", res)

        # 查看用户列表
        res = self.session.get(f"{self.base_url}/{TEST_REALM}/users")
        self.log("查看用户列表", res)

    # --- 5. 清理租户 ---
    def cleanup(self):
        print("\n=== [清理: 删除租户] ===")
        res = self.session.delete(f"{self.base_url}/tenants/{TEST_REALM}")
        self.log("删除测试租户", res)

    # --- 6. 导出 OpenAPI ---
    def test_export_spec(self):
        print("\n=== [场景 5: 导出定义文件] ===")
        res = self.session.get(f"{self.base_url}/export-spec")
        if res.status_code == 200:
            with open("keycloak_api_spec.json", "w", encoding="utf-8") as f:
                json.dump(res.json(), f, indent=2, ensure_ascii=False)
            print("✅ OpenAPI JSON 已导出至当前目录")


def run_all():
    tester = KeycloakWrapperTester()
    try:
        tester.test_tenant_management()
        tester.test_role_management()
        tester.test_idp_management()
        tester.test_query_operations()
        tester.test_export_spec()
    finally:
        # 无论成功失败，尝试清理环境
        tester.cleanup()


if __name__ == "__main__":
    run_all()
