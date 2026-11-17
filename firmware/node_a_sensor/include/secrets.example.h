#pragma once
#include <stdint.h>

// Copy file nay thanh "secrets.h" trong cung thu muc include/
// va dien dia chi STA MAC cua Node B (lay tu Serial Monitor cua Node B khi khoi dong).
// Khong commit file secrets.h len Git!

static const uint8_t NODE_B_MAC_ADDR[6] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};
