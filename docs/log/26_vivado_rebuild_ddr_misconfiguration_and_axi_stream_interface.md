# 26. Vivado Rebuild — DDR Part Misconfiguration and AXI-Stream Interface Connection Rules

- 작성일: 2026-05-12
- 선행 문서: `25_axi_stream_tlast_deadlock_troubleshooting.md`

---

## 배경

`25_axi_stream_tlast_deadlock_troubleshooting.md`에서 TLAST 데드락을 분석하고 RTL을 재설계했다. 이를 반영한 비트스트림 재생성을 위해 Vivado 프로젝트를 열고 재빌드를 시도했다.

---

## 문제 1: DDR 파트가 Z7-10 파트로 오설정

**증상**

`bd_fir_dma.tcl`로 Block Design을 생성할 때 PS7의 DDR 파트가 `MT41J128M8 JP-125`로 설정되어 있었다.

```tcl
get_property CONFIG.PCW_UIPARAM_DDR_PARTNO [get_bd_cells /processing_system7_0]
MT41J128M8 JP-125   ← 잘못된 파트 (Zybo Z7-10 DDR)
```

**원인**

`bd_fir_dma.tcl` 생성 시 보드 파일이 올바르게 적용되지 않아 Z7-10의 DDR 파트(`MT41J128M8`, 128Mx8)가 들어갔다. 실제 보드(Zybo Z7-20)의 DDR은 `MT41K256M16`(256Mx16)이다.

**해결**

Vivado BD 다이어그램 상단의 녹색 배너에서 보드 파일 적용 버튼을 눌러 Z7-20 보드 설정을 강제 적용.

검증 명령어:

```tcl
get_property CONFIG.PCW_UIPARAM_DDR_PARTNO [get_bd_cells /processing_system7_0]
MT41K256M16 RE-125  ← 올바른 파트 (Zybo Z7-20 DDR)
```

**[의견]** 이 문제가 기존 S2MM 타임아웃과 UART 무응답의 원인 중 하나였을 가능성이 있다. `ps7_init.tcl`은 DDR 파트 정보를 기반으로 DDR 타이밍 레지스터(CAS latency, tRCD, tRP 등)를 설정한다. Z7-10 파트로 Z7-20 보드를 초기화하면 DDR 타이밍 오설정 → DDR 동작 불안정 → DMA 전송 실패로 이어질 수 있다.

---

## 문제 2: AXI-Stream 번들을 개별 신호로 열어 연결하면 안 된다

**증상**

BD에서 FIR IP의 M_AXIS 출력과 AXI DMA의 S_AXIS_S2MM 포트를 연결할 때, 번들을 펼쳐(expand) 개별 신호(`tdata`, `tvalid`, `tready`, `tlast`)를 하나씩 연결하면 안 된다는 것을 확인했다. 번들끼리 직접 연결해야 한다.

**원인**

Vivado IP Integrator에서 AXI-Stream 포트는 단순한 wire 묶음이 아니라 **인터페이스(Interface)** 로 관리된다. 번들을 펼쳐 개별 신호로 연결하면:

1. Vivado가 해당 연결을 AXI-Stream 프로토콜 연결로 인식하지 못한다.
2. 인터페이스 수준의 프로토콜 검증(데이터 폭 일치, TUSER/TKEEP 선택적 신호 처리 등)이 동작하지 않는다.
3. AXI DMA는 `S_AXIS_S2MM` 인터페이스 단위로 연결을 인식하므로, 개별 wire로 연결하면 DMA 내부에서 핸드셰이킹이 정상 작동하지 않을 수 있다.
4. IP Integrator의 자동 검증 규칙(bd_rule)도 인터페이스 연결에만 적용된다.

**해결**

번들을 펼치지 않고 `M_AXIS` ↔ `S_AXIS_S2MM` 인터페이스를 통째로 연결한다.

---

## 현재 상태 (2026-05-13)

| 항목                       | 상태                   |
| -------------------------- | ---------------------- |
| DDR 파트 Z7-20으로 수정    | ✅                     |
| AXI-Stream 인터페이스 연결 | ✅ 번들 단위 연결 완료 |
| 비트스트림 생성            | ✅ 재빌드 완료         |
| 보드 검증 (UART 응답)      | ❌ JTAG 로딩 미해결 — SD카드 부팅으로 전환 |

DDR byte[3] 오염 문제 상세 디버깅(Phase 1-9) 및 최종 결론 → `27_ddr_msb_corruption_investigation.md`

---

## 핵심 교훈

1. **DDR 파트 불일치는 `ps7_init.tcl` 오설정으로 이어진다.** 보드 파일이 올바르게 적용됐는지 `get_property CONFIG.PCW_UIPARAM_DDR_PARTNO`로 항상 확인해야 한다.
2. **Vivado BD에서 AXI-Stream은 인터페이스 단위로 연결해야 한다.** 개별 신호 연결은 IP Integrator의 프로토콜 검증을 우회하고 DMA 동작을 보장하지 않는다.
