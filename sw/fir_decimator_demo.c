#include <math.h>
#include <stdint.h>
#include <stdlib.h>

#include "xil_cache.h"
#include "xparameters.h"
#include "xuartps.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* --- 수정 가능한 설정 -------------------------------------------------- */
#define UART_BAUD_RATE 115200                   /* 느리면 921600으로 변경 */
#define UART_DEVICE_ID XPAR_XUARTPS_1_DEVICE_ID /* Zybo Z7-20 USB-UART 브릿지 \
                                                 */

#define DMA_BASE 0x40400000u /* bd_fir_dma.tcl assign_bd_address 기준 */
#define N_IN 8192            /* 입력 샘플 수 */
#define N_OUT 4096           /* 출력 샘플 수 (N_IN / M, M=2) */
#define FS_HZ 100000000.0f   /* 샘플링 주파수 100MHz */
#define MAX_TONES 8          /* 최대 톤 개수 */
#define MAGIC 0xDEADBEEFu    /* UART 패킷 시작 마커 */
/* ---------------------------------------------------------------------- */

/* AXI DMA 레지스터 오프셋 (PG021) */
#define MM2S_DMACR 0x00u
#define MM2S_DMASR 0x04u
#define MM2S_SA 0x18u
#define MM2S_LENGTH 0x28u
#define S2MM_DMACR 0x30u
#define S2MM_DMASR 0x34u
#define S2MM_DA 0x48u
#define S2MM_LENGTH 0x58u

#define DMA_RS_BIT (1u << 0)
#define DMA_IDLE_BIT (1u << 1)
#define DMA_REG(off) (*(volatile uint32_t*)(DMA_BASE + (off)))

/* 전역 버퍼: 16KB + 8KB → 스택 한계 초과, BSS(DDR)에 배치
 * aligned(32): Cortex-A9 캐시 라인 크기, flush/invalidate 경계 보장 */
static int16_t __attribute__((aligned(32))) src_buf[N_IN];
static int16_t __attribute__((aligned(32))) dst_buf[N_OUT];

static XUartPs uart_inst;
static uint32_t uart_base;

static void uart_init(void) {
  XUartPs_Config* cfg = XUartPs_LookupConfig(UART_DEVICE_ID);
  XUartPs_CfgInitialize(&uart_inst, cfg, cfg->BaseAddress);
  XUartPs_SetBaudRate(&uart_inst, UART_BAUD_RATE);
  uart_base = cfg->BaseAddress;
}

static inline void uart_putb(uint8_t b) { XUartPs_SendByte(uart_base, b); }

static inline uint8_t uart_getb(void) { return XUartPs_RecvByte(uart_base); }

/* PC → PS: "<n> <f1> <f2> ... <fn>\n"  (text, Hz)
 * text 선택 이유: minicom에서 직접 타이핑해 디버깅 가능 */
static int uart_recv_cmd(float* freqs) {
  char buf[256];
  int i = 0;

  while (1) {
    char c = (char)uart_getb();
    if (c == '\n' || c == '\r') break;
    if (i < 255) buf[i++] = c;
  }
  buf[i] = '\0';

  char *ptr = buf, *end;
  int n_tones = (int)strtol(ptr, &end, 10);
  ptr = end;

  if (n_tones < 1) n_tones = 1;
  if (n_tones > MAX_TONES) n_tones = MAX_TONES;

  for (int j = 0; j < n_tones; j++) {
    freqs[j] = strtof(ptr, &end);
    ptr = end;
  }
  return n_tones;
}

/* 진폭 = 0.9 / n_tones: 합산 최대 0.9로 Q1.15 클리핑 방지 */
static void gen_multitone(const float* freqs, int n_tones) {
  float amp = 0.9f / (float)n_tones;

  for (int n = 0; n < N_IN; n++) {
    float x = 0.0f;
    for (int k = 0; k < n_tones; k++)
      x += amp * sinf(2.0f * (float)M_PI * freqs[k] / FS_HZ * (float)n);

    int32_t q = (int32_t)roundf(x * 32768.0f);
    if (q > 32767) q = 32767;
    if (q < -32768) q = -32768;
    src_buf[n] = (int16_t)q;
  }
}

static void dma_run(void) {
  /* DMA는 캐시를 우회해 DDR 직접 접근 → flush로 CPU 캐시를 DDR에 반영 */
  Xil_DCacheFlushRange((UINTPTR)src_buf, N_IN * sizeof(int16_t));

  /* S2MM 먼저: MM2S 시작 후 FIR 출력이 즉시 나오므로 수신 채널이 먼저 열려야 함
   */
  DMA_REG(S2MM_DMACR) = DMA_RS_BIT;
  DMA_REG(S2MM_DA) = (uint32_t)(UINTPTR)dst_buf;
  DMA_REG(S2MM_LENGTH) = N_OUT * sizeof(int16_t);

  DMA_REG(MM2S_DMACR) = DMA_RS_BIT;
  DMA_REG(MM2S_SA) = (uint32_t)(UINTPTR)src_buf;
  DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);

  while (!(DMA_REG(MM2S_DMASR) & DMA_IDLE_BIT));
  while (!(DMA_REG(S2MM_DMASR) & DMA_IDLE_BIT));

  /* DMA가 DDR에 쓴 결과를 캐시에서 버려야 CPU가 최신 데이터를 읽음 */
  Xil_DCacheInvalidateRange((UINTPTR)dst_buf, N_OUT * sizeof(int16_t));
}

/* PS → PC: [magic 4B][n_samples 4B][int16 × N_OUT] (binary, little-endian) */
static void uart_send_result(void) {
  const uint32_t magic = MAGIC;
  const uint32_t n = N_OUT;

  for (int i = 0; i < 4; i++) uart_putb(((const uint8_t*)&magic)[i]);
  for (int i = 0; i < 4; i++) uart_putb(((const uint8_t*)&n)[i]);
  for (int i = 0; i < N_OUT; i++) {
    uart_putb(((const uint8_t*)&dst_buf[i])[0]);
    uart_putb(((const uint8_t*)&dst_buf[i])[1]);
  }
}

int main(void) {
  uart_init();

  while (1) {
    float freqs[MAX_TONES];
    int n_tones = uart_recv_cmd(freqs);
    gen_multitone(freqs, n_tones);
    dma_run();
    uart_send_result();
  }

  return 0;
}
