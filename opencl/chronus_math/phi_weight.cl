__kernel void chronus_phi_weight(__global const uint*index,__global float*out){uint i=get_global_id(0);out[i]=powr(1.6180339887498948482f,-convert_float(index[i]+1));}
