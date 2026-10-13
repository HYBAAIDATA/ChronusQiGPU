// Exact u64 fast doubling. Certified only for n <= 93.
inline ulong2 fib_pair(uint n){ulong a=0,b=1;for(int bit=31-clz(n|1);bit>=0;--bit){ulong c=a*((b<<1)-a),d=a*a+b*b;if((n>>bit)&1){a=d;b=c+d;}else{a=c;b=d;}}return (ulong2)(a,b);}
__kernel void chronus_fibonacci(__global const uint*n,__global ulong*out){uint i=get_global_id(0);out[i]=fib_pair(n[i]).x;}
