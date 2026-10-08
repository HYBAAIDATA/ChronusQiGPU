#include <cstdint>
#include <iostream>
#include <vector>
#include <stdexcept>
#include "mla1517.h"

static std::pair<uint64_t,uint64_t> fib_pair(unsigned n) {
    uint64_t a=0,b=1;
    for (unsigned i=0;i<n;i++) { uint64_t t=a+b; a=b; b=t; }
    return {a,b};
}
uint64_t mla_fibonacci(unsigned n) { return fib_pair(n).first; }
uint64_t mla_lucas(unsigned n) {
    uint64_t a=2,b=1;
    for (unsigned i=0;i<n;i++) { uint64_t t=a+b; a=b; b=t; }
    return a;
}
int64_t mla_cassini(unsigned n) {
    if (n==0) return 1;
    auto fm=fib_pair(n-1).first;
    auto f=fib_pair(n).first;
    auto fp=fib_pair(n+1).first;
    return static_cast<int64_t>(fm*fp-f*f);
}
uint64_t mla_zeckendorf(unsigned n) {
    if (n==0) return 0;
    std::vector<uint64_t> f{1,2};
    while (f.back() <= n) f.push_back(f[f.size()-1]+f[f.size()-2]);
    uint64_t rem=n, mask=0;
    for (int i=static_cast<int>(f.size())-1;i>=0;i--) {
        if (f[i] <= rem) { rem-=f[i]; mask |= (uint64_t(1)<<i); }
    }
    if (rem!=0) throw std::runtime_error("Zeckendorf remainder");
    return mask;
}
static uint64_t zeck_decode(uint64_t mask) {
    std::vector<uint64_t> f{1,2};
    while ((uint64_t(1)<<(f.size()-1)) <= mask) f.push_back(f[f.size()-1]+f[f.size()-2]);
    uint64_t out=0;
    for (unsigned i=0;i<f.size();i++) if ((mask>>i)&1) out+=f[i];
    return out;
}
int main() {
    bool cass=true, luc=true, z=true;
    for (unsigned n=1;n<=40;n++) {
        cass = cass && (mla_cassini(n)==(n%2 ? -1 : 1));
        auto p=fib_pair(n);
        luc = luc && (mla_lucas(n)==fib_pair(n-1).first+fib_pair(n+1).first); // L_n=F_{n-1}+F_{n+1}
    }
    for (unsigned n=1;n<=1000;n++) z = z && (zeck_decode(mla_zeckendorf(n))==n);
    std::cout << "{\"cassini\":" << (cass?"true":"false")
              << ",\"lucas\":" << (luc?"true":"false")
              << ",\"zeckendorf\":" << (z?"true":"false")
              << ",\"fibonacci_15\":" << mla_fibonacci(15)
              << ",\"lucas_15\":" << mla_lucas(15) << "}\n";
    return (cass&&luc&&z) ? 0 : 1;
}
