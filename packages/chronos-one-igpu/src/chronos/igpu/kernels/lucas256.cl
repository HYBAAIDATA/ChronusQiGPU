/* Exact Z/(2^256) Lucas fast doubling. One work item per rung.
 * Host certificate/PrimeROM stages remain host-owned and independently verify.
 */
typedef struct { uint w[8]; } u256;
inline u256 z256(){u256 x;for(int i=0;i<8;i++)x.w[i]=0;return x;}
inline u256 a256(u256 a,u256 b){u256 r;ulong c=0;for(int i=0;i<8;i++){ulong t=(ulong)a.w[i]+b.w[i]+c;r.w[i]=(uint)t;c=t>>32;}return r;}
inline u256 s256(u256 a,u256 b){u256 r;ulong borrow=0;for(int i=0;i<8;i++){ulong x=a.w[i];ulong y=(ulong)b.w[i]+borrow;r.w[i]=(uint)(x-y);borrow=x<y;}return r;}
inline u256 m256(u256 a,u256 b){u256 r=z256();for(int i=0;i<8;i++){ulong c=0;for(int j=0;j<8-i;j++){ulong t=(ulong)a.w[i]*b.w[j]+r.w[i+j]+c;r.w[i+j]=(uint)t;c=t>>32;}}return r;}
inline u256 lucas256(ulong n){u256 a=z256(),b=z256();b.w[0]=1;for(int k=63;k>=0;k--){u256 c=m256(a,s256(a256(b,b),a));u256 d=a256(m256(a,a),m256(b,b));if((n>>k)&1){a=d;b=a256(c,d);}else{a=c;b=d;}}return s256(a256(b,b),a);}
__kernel void chronos_lucas256(__global const ulong *rungs,__global uint *out,uint count){uint id=(uint)get_global_id(0);if(id>=count)return;u256 value=lucas256(rungs[id]);for(int j=0;j<8;j++)out[id*8+j]=value.w[j];}
