# step1b: datapath/macro 블럭 자동 배치 (수동 드래그 대체)
# 인자 오류가 나면 콘솔에서 help place_macros 로 정확한 문법 확인
place_macros -partition $TOP_MODULE
puts "step1b done — GUI에서 블럭들이 칩 안에 배치됐는지 확인 후: source $S/nitro_step2_rows.tcl"
