# build_fir_decimator_demo.pyplatform
# Usage: vitis -s vitis/build_fir_decimator_demo.py  (repo root에서 실행)
#
# 산출물: build/output/fir_decimator_demo.elf

import vitis
import os
import glob
import shutil

REPO_ROOT  = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
XSA        = os.path.join(REPO_ROOT, "build", "output", "bd_fir_dma_wrapper.xsa")
WORKSPACE  = os.path.join(REPO_ROOT, "build", "vitis")
OUT_DIR    = os.path.join(REPO_ROOT, "build", "output")
SRC        = os.path.join(REPO_ROOT, "sw", "fir_decimator_demo.c")

os.makedirs(OUT_DIR,   exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)

client = vitis.create_client()
client.update_workspace(WORKSPACE)

# 플랫폼 생성 (XSA → BSP)
 = client.create_platform_component(
    name         = "fir_dma_platform",
    hw_design    = XSA,
    os           = "standalone",
    cpu          = "ps7_cortexa9_0",
    no_boot_bsp  = True,
    generate_dtb = False,
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
app.set_app_config(key="USER_LINK_LIBRARIES", values=["m"])

# 빌드
app.build()

vitis.dispose()

# ELF을 build/output/으로 복사 (Debug/ 또는 build/ 둘 다 시도)
elfs = glob.glob(os.path.join(WORKSPACE, "fir_decimator_demo", "*", "fir_decimator_demo.elf"))
if elfs:
    shutil.copy2(elfs[0], os.path.join(OUT_DIR, "fir_decimator_demo.elf"))
    print("")
    print("=== 빌드 완료 ===")
    print(f"ELF: {OUT_DIR}/fir_decimator_demo.elf")
else:
    print(f"WARNING: ELF not found — {WORKSPACE} 아래를 직접 확인하세요")
