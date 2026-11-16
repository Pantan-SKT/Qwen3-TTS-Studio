"""Check torch CUDA readiness independently of web server or model downloads."""
import json
import sys

def get_diagnostics():
    result = {"python": sys.version.split()[0], "torch": None, "torch_cuda_build": None,
              "cuda_available": False, "gpu_name": None, "error": None}
    try:
        import torch
        result["torch"] = torch.__version__
        result["torch_cuda_build"] = torch.version.cuda
        result["cuda_available"] = bool(torch.cuda.is_available())
        if result["cuda_available"]:
            result["gpu_name"] = torch.cuda.get_device_name(0)
            # Exercise a trivial CUDA kernel to identify architecture / driver incompatibility.
            result["test_result"] = float((torch.ones(1, device="cuda") * 2).cpu()[0])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["cuda_available"] = False
    return result

if __name__ == "__main__":
    info = get_diagnostics()
    print(json.dumps(info, indent=2, ensure_ascii=False))
    if not info["cuda_available"]:
        print("[ERROR] CUDA unavailable. Run cuda-repair.bat (requires NVIDIA driver).")
    else:
        print("[OK] NVIDIA CUDA acceleration is ready.")
    sys.exit(0 if info["cuda_available"] else 2)
