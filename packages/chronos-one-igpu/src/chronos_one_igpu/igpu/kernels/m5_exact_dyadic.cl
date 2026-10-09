/* Exact Q(sqrt(2),i) gate step, common power-of-two denominator.
 * No floating types, atomics/reductions on amplitudes, or fast-math.
 * Each output work item gathers immutable input; no races on coefficients.
 */
#define QMAX 9223372036854775807L
#define QMIN (-9223372036854775807L-1L)
inline long qadd(long a,long b,__global volatile int *error) {
  if((b>0 && a>QMAX-b)||(b<0 && a<QMIN-b)){atomic_or(error,1);return 0;}
  return a+b;
}
inline long qneg(long a,__global volatile int *error) {
  if(a==QMIN){atomic_or(error,1);return 0;}return -a;
}
inline long qtwice(long a,__global volatile int *error) {
  if(a>QMAX/2 || a<QMIN/2){atomic_or(error,1);return 0;}return a*2;
}
__kernel void m5_gate_step(__global const long *src,__global long *dst,
 __global const int *plan,const int stage,const int dimension,
 __global volatile int *error) {
  int j=(int)get_global_id(0);if(j>=dimension)return;
  int gate=plan[stage*3],a=plan[stage*3+1],b=plan[stage*3+2],k=j;
  if(gate==1)k=j^(1<<a); /* X */
  if(gate==7 && (j&(1<<a)))k=j^(1<<b); /* CX */
  if(gate==9 && (!!(j&(1<<a))!=!!(j&(1<<b))))k=j^((1<<a)|(1<<b));
  long v[4];for(int r=0;r<4;r++)v[r]=src[k*4+r];
  if(gate==0){ /* H: denominator exponent increases once globally */
    int lo=j&~(1<<a),hi=lo|(1<<a);long sums[4];
    for(int r=0;r<4;r++)sums[r]=qadd(src[lo*4+r],(j&(1<<a))?qneg(src[hi*4+r],error):src[hi*4+r],error);
    v[0]=qtwice(sums[1],error);v[1]=sums[0];
    v[2]=qtwice(sums[3],error);v[3]=sums[2];
  } else if(gate==5 || gate==6){ /* T, Tdag */
    if(j&(1<<a)){
      long x0=v[0],x1=v[1],x2=v[2],x3=v[3];
      long c=gate==5?x2:qneg(x2,error),d=gate==5?x3:qneg(x3,error);
      long aa=gate==5?x0:qneg(x0,error),bb=gate==5?x1:qneg(x1,error);
      v[0]=qtwice(qadd(x1,qneg(d,error),error),error);v[1]=qadd(x0,qneg(c,error),error);
      v[2]=qtwice(qadd(bb,x3,error),error);v[3]=qadd(aa,x2,error);
    }else for(int r=0;r<4;r++)v[r]=qtwice(v[r],error);
  } else if((gate==3 || gate==4) && (j&(1<<a))){ /* S,Sdag */
    long x0=v[0],x1=v[1],x2=v[2],x3=v[3];
    v[0]=gate==3?qneg(x2,error):x2;v[1]=gate==3?qneg(x3,error):x3;
    v[2]=gate==3?x0:qneg(x0,error);v[3]=gate==3?x1:qneg(x1,error);
  } else if((gate==2 && (j&(1<<a)))||(gate==8 && (j&(1<<a)) && (j&(1<<b)))) {
    for(int r=0;r<4;r++)v[r]=qneg(v[r],error);
  }
  if(gate<0||gate>9){atomic_or(error,2);return;}
  for(int r=0;r<4;r++)dst[j*4+r]=v[r];
}
