# build_fir_decimator_demo.py
# Usage: vitis -s vitis/build_fir_decimator_demo.py  (repo root에서 실행)
# 빌드 산출물: /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_demo/

import vitis
import os

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
XSA       = "/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_trans_n43/bd_fir_dma_wrapper.xsa"
WORKSPACE = "/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_demo"
SRC       = os.path.join(REPO_ROOT, "ps", "fir_decimator_demo.c")

client = vitis.create_client()
client.set_workspace(WORKSPACE)

# 플랫폼 생성 (XSA → BSP)
platform = client.create_platform_component(
    name      = "fir_dma_platform",
    hw_design = XSA,
    os        = "standalone",
    cpu       = "ps7_cortexa9_0",
)
platform.build()

# 애플리케이션 생성
app = client.create_app_component(
    name     = "fir_decimator_demo",
    platform = os.path.join(WORKSPACE, "fir_dma_platform", "export", "fir_dma_platform", "fir_dma_platform.xpfm"),
    domain   = "standalone_ps7_cortexa9_0",
    template = "empty_application",
)

# C 소스 추가
app.import_files(from_loc=os.path.dirname(SRC), files=[os.path.basename(SRC)])

# math 라이브러리 링크 (-lm)
app.set_property("USER_LINK_FLAGS", "-lm")

# 빌드
app.build()

print("")
print("=== 빌드 완료 ===")
print(f"ELF: {WORKSPACE}/fir_decimator_demo/build/fir_decimator_demo.elf")

vitis.dispose()
