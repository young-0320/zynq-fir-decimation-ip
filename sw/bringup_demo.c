/*
 * bringup_demo.c
 *
 * 목적: JTAG ELF 로드 + UART 통신 라인 단독 검증
 *       DMA/FIR IP 일절 없음. UART만 동작하면 통과.
 *
 * 기대 동작:
 *   1. 부팅 즉시 "BRINGUP OK\r\n" 출력
 *   2. 1초 주기 heartbeat "ALIVE <n>\r\n" 출력
 *   3. UART로 받은 바이트를 그대로 echo
 *
 * 검증 방법:
 *   minicom -D /dev/ttyUSB1 -b 115200
 *   → "BRINGUP OK" 보이면 ELF 로드 및 UART 정상
 *   → 키 입력 echo 확인
 */

#include <stdint.h>
#include "xparameters.h"
#include "xuartps.h"

#define UART_DEVICE_ID 0
#define UART_BAUD_RATE 115200

/* FCLK0 = 100MHz, 대략적 루프 카운트로 1초 추정 */
#define DELAY_1S_LOOPS 50000000u

static XUartPs uart_inst;
static uint32_t uart_base;

static void uart_init(void) {
    XUartPs_Config *cfg = XUartPs_LookupConfig(UART_DEVICE_ID);
    XUartPs_CfgInitialize(&uart_inst, cfg, cfg->BaseAddress);
    XUartPs_SetBaudRate(&uart_inst, UART_BAUD_RATE);
    uart_base = cfg->BaseAddress;
}

static void uart_putb(uint8_t b) { XUartPs_SendByte(uart_base, b); }

static void uart_puts(const char *s) {
    while (*s) uart_putb((uint8_t)*s++);
}

/* 부호 없는 정수를 10진 문자열로 출력 */
static void uart_putu(uint32_t v) {
    char buf[11];
    int i = 10;
    buf[10] = '\0';
    if (v == 0) { uart_putb('0'); return; }
    while (v && i > 0) { buf[--i] = '0' + (v % 10); v /= 10; }
    uart_puts(&buf[i]);
}

static int uart_rx_ready(void) {
    return XUartPs_IsReceiveData(uart_base);
}

int main(void) {
    uart_init();
    uart_puts("BRINGUP OK\r\n");

    uint32_t count = 0;
    uint32_t loop  = 0;

    while (1) {
        /* heartbeat: 약 1초마다 출력 */
        if (++loop >= DELAY_1S_LOOPS) {
            loop = 0;
            uart_puts("ALIVE ");
            uart_putu(count++);
            uart_puts("\r\n");
        }

        /* UART echo */
        if (uart_rx_ready()) {
            uint8_t b = XUartPs_RecvByte(uart_base);
            uart_putb(b);
        }
    }

    return 0;
}
