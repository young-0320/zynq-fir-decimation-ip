# v1/v2 공용 clock constraint — 두 런이 반드시 같은 period를 쓰도록 파일을 공유한다.
# period sweep 시 이 파일의 값만 바꾸고 v1/v2를 연달아 돌린다 (단위: ps).
# 시작 20000ps(50MHz) → 15000(66.7MHz) → 12000(83.3MHz) → 10000(100MHz) → 8000(125MHz)
# 순으로 줄여가며 timing이 깨지는 지점을 찾고, 첫 FAIL이 나오면 마지막 PASS와의
# 사이를 이분탐색으로 좁힌다. 범위 근거는 README §2 참고.
create_clock -name clk -period 12000.0 [get_ports clk]
