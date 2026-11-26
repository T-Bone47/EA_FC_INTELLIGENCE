"""Environment probe and commercial-safe / AGPL-segregated training recipe builder."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

from backend.cv_training.manifest import EA_FC_CLASSES


def _pkg_version(name: str) -> Optional[str]:
    if importlib.util.find_spec(name) is None:
        return None
    try:
        mod = __import__(name)
        return str(getattr(mod, "__version__", "installed"))
    except Exception:
        return "installed"


def probe_local_cv_environment() -> Dict[str, Any]:
    """Probes real local CV packages, OpenCL/CUDA availability, and model checkpoint files."""
    cv2_ver = _pkg_version("cv2")
    opencl_available = False
    opencl_device = "CPU_ONLY"
    if cv2_ver:
        try:
            import cv2
            opencl_available = bool(cv2.ocl.haveOpenCL())
            if opencl_available:
                cv2.ocl.setUseOpenCL(True)
                dev = cv2.ocl.Device.getDefault()
                opencl_device = dev.name() if dev else "OpenCL GPU"
        except Exception:
            opencl_available = False

    torch_ver = _pkg_version("torch")
    cuda_available = False
    gpu_name = None
    vram_mb = None
    if torch_ver:
        try:
            import torch
            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                props = torch.cuda.get_device_properties(0)
                gpu_name = props.name
                vram_mb = int(props.total_memory // (1024 * 1024))
        except Exception:
            pass

    models_dir = Path(__file__).resolve().parents[1] / "models"
    weights_found = (
        [p.name for p in models_dir.glob("*") if p.suffix.lower() in {".onnx", ".pt", ".pth"}]
        if models_dir.exists()
        else []
    )

    return {
        "opencv": cv2_ver,
        "pyav": _pkg_version("av"),
        "scipy": _pkg_version("scipy"),
        "scikit_learn": _pkg_version("sklearn"),
        "torch": torch_ver,
        "torchvision": _pkg_version("torchvision"),
        "onnxruntime": _pkg_version("onnxruntime"),
        "ultralytics": _pkg_version("ultralytics"),
        "opencl_available": opencl_available,
        "opencl_device": opencl_device,
        "cuda_available": cuda_available,
        "cuda_gpu_name": gpu_name,
        "cuda_vram_mb": vram_mb,
        "models_dir": str(models_dir),
        "weights_present": weights_found,
        "training_ready_for_pytorch_gradient_descent": bool(torch_ver and cuda_available),
        "onnx_inference_ready_via_opencv_dnn": bool(cv2_ver),
    }


class TrainingRecipeSpec(BaseModel):
    framework: Literal["YOLOX_APACHE2", "ULTRALYTICS_AGPL3_OPT_IN"] = "YOLOX_APACHE2"
    license_name: str
    commercial_safe: bool
    requires_explicit_agpl_opt_in: bool = False
    backbone: str
    input_size_player: Tuple[int, int] = (640, 640)
    input_size_small_ball: Tuple[int, int] = (960, 960)
    batch_size_4gb_vram: int = 4
    grad_accumulation_steps: int = 4
    fp16_mixed_precision: bool = True
    epochs: int = 60
    early_stopping_patience_epochs: int = 8
    early_stopping_min_delta: float = 0.003
    camera_stream: Literal["BROADCAST", "MINIMAP_ROI"] = "BROADCAST"
    resume_checkpoint_path: Optional[str] = None
    onnx_opset: int = 12
    target_onnx_path: str
    classes: Dict[int, str] = Field(default_factory=lambda: dict(EA_FC_CLASSES))
    yolo_data_yaml: str
    training_command: str
    limitations: List[str] = Field(default_factory=list)


def build_training_recipe(
    *,
    dataset_root: str = "data/cv_datasets/ea_fc_v1",
    framework: Literal["YOLOX_APACHE2", "ULTRALYTICS_AGPL3_OPT_IN"] = "YOLOX_APACHE2",
    accept_agpl_copyleft: bool = False,
) -> TrainingRecipeSpec:
    """Generates a 4GB-VRAM tuned EA FC training recipe with strict OSS license separation."""
    if framework == "ULTRALYTICS_AGPL3_OPT_IN" and not accept_agpl_copyleft:
        raise PermissionError(
            "Ultralytics YOLO carries AGPL-3.0 obligations for network-hosted commercial deployments. "
            "Pass accept_agpl_copyleft=True explicitly or use the default YOLOX Apache-2.0 recipe."
        )

    data_yaml = "\n".join(
        [
            f"path: {dataset_root}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            *[f"  {cid}: {cname}" for cid, cname in EA_FC_CLASSES.items()],
        ]
    )

    if framework == "YOLOX_APACHE2":
        return TrainingRecipeSpec(
            framework="YOLOX_APACHE2",
            license_name="Apache-2.0",
            commercial_safe=True,
            requires_explicit_agpl_opt_in=False,
            backbone="yolox-s",
            input_size_player=(640, 640),
            input_size_small_ball=(960, 960),
            batch_size_4gb_vram=4,
            grad_accumulation_steps=4,
            fp16_mixed_precision=True,
            epochs=60,
            onnx_opset=12,
            target_onnx_path="backend/models/fc_detector.onnx",
            yolo_data_yaml=data_yaml,
            training_command=(
                "python -m yolox.tools.train -f configs/yolox_s_eafc.py -d 1 -b 4 --fp16 "
                "-o --cache ram && python -m yolox.tools.export_onnx "
                "--output-name backend/models/fc_detector.onnx -f configs/yolox_s_eafc.py "
                "-c YOLOX_outputs/yolox_s_eafc/best_ckpt.pth --opset 12"
            ),
            limitations=[
                "Requires PyTorch + CUDA runtime (not bundled in zero-budget CPU backend) and annotated EA FC broadcast frames.",
                "Exported YOLOX ONNX uses decoded class/box tensor layout expected by PixelPerceptionExtractor._detect_with_onnx().",
            ],
        )

    return TrainingRecipeSpec(
        framework="ULTRALYTICS_AGPL3_OPT_IN",
        license_name="AGPL-3.0 (Copyleft Opt-In)",
        commercial_safe=False,
        requires_explicit_agpl_opt_in=True,
        backbone="yolo11s",
        input_size_player=(640, 640),
        input_size_small_ball=(960, 960),
        batch_size_4gb_vram=4,
        grad_accumulation_steps=4,
        fp16_mixed_precision=True,
        epochs=60,
        onnx_opset=12,
        target_onnx_path="backend/models/fc_detector.onnx",
        yolo_data_yaml=data_yaml,
        training_command=(
            f"yolo detect train data={dataset_root}/data.yaml model=yolo11s.pt imgsz=640 "
            "batch=4 half=True epochs=60 project=backend/models/runs name=eafc_agpl_optin && "
            "yolo export model=backend/models/runs/eafc_agpl_optin/weights/best.pt format=onnx imgsz=640 opset=12"
        ),
        limitations=[
            "AGPL-3.0 dependency: isolate external training scripts from proprietary SaaS runtime.",
        ],
    )
