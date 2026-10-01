#ifndef MLA1517_H
#define MLA1517_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
uint64_t mla_fibonacci(unsigned n);
uint64_t mla_lucas(unsigned n);
int64_t mla_cassini(unsigned n);
uint64_t mla_zeckendorf(unsigned n);
#ifdef __cplusplus
}
#endif
#endif
