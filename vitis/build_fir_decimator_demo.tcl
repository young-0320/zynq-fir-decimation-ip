# build_fir_decimator_demo.tcl
# Usage: xsct vivado/build_fir_decimator_demo.tcl  (repo root에서 실행)
# 빌드 산출물: /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_demo/

set REPO_ROOT  [file normalize [file dirname [file dirname [info script]]]]
set XSA        /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_trans_n43/bd_fir_dma_wrapper.xsa
set WORKSPACE  /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_demo
set SRC        $REPO_ROOT/ps/fir_decimator_demo.c

setws $WORKSPACE

platform create -name fir_dma_platform \
    -hw $XSA \
    -os standalone \
    -proc ps7_cortexa9_0 \
    -no-boot-bsp

platform generate

app create -name fir_decimator_demo \
    -platform fir_dma_platform \
    -domain standalone_ps7_cortexa9_0 \
    -template {Empty Application(C)}

importsources -name fir_decimator_demo -path $SRC

app config -name fir_decimator_demo libs m

app build -name fir_decimator_demo

puts ""
puts "=== 빌드 완료 ==="
puts "ELF: $WORKSPACE/fir_decimator_demo/Debug/fir_decimator_demo.elf"
