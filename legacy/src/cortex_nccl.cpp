#include "cortex_nccl.h"
#include <stdexcept>

#define NCCL_CHECK(cmd) do { \
    ncclResult_t res = cmd; \
    if (res != ncclSuccess) { \
        throw std::runtime_error(std::string("NCCL Error: ") + ncclGetErrorString(res)); \
    } \
} while(0)

namespace cortex {

void nccl_async_allreduce(
    at::Tensor tensor,
    intptr_t comm_handle,
    int op_type
) {
    TORCH_CHECK(tensor.is_cuda(), "Input tensor must reside on CUDA device.");
    
    ncclComm_t comm = reinterpret_cast<ncclComm_t>(comm_handle);
    cudaStream_t stream = c10::cuda::getCurrentCUDAStream().stream();

    ncclDataType_t nccl_dtype;
    if (tensor.scalar_type() == at::kByte) {
        nccl_dtype = ncclUint8;
    } else if (tensor.scalar_type() == at::kHalf) {
        nccl_dtype = ncclFloat16;
    } else if (tensor.scalar_type() == at::kFloat8_e4m3fn || tensor.scalar_type() == at::kFloat8_e5m2) {
        nccl_dtype = ncclUint8; // NCCL handles raw FP8 byte transfers bitwise
    } else {
        nccl_dtype = ncclFloat32;
    }

    ncclRedOp_t red_op = (op_type == 0) ? ncclSum : ncclAvg;

    NCCL_CHECK(ncclAllReduce(
        tensor.data_ptr(),
        tensor.data_ptr(),
        tensor.numel(),
        nccl_dtype,
        red_op,
        comm,
        stream
    ));
}

} // namespace cortex

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.doc() = "Cortex NCCL Stream-Aware Binding Plugin";
    m.def("async_allreduce", &cortex::nccl_async_allreduce, 
          "Asynchronous stream-aware NCCL AllReduce binding",
          py::arg("tensor"), py::arg("comm_handle"), py::arg("op_type") = 0);
}
