from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_shared_path = (
    Path(__file__).resolve().parents[3]
    / "federated_learning"
    / "server_final"
    / "runtime_core"
    / "security_layers"
    / "device_fingerprint.py"
)
_spec = spec_from_file_location("shared_device_fingerprint", _shared_path)
_module = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)

for _name, _value in _module.__dict__.items():
    if not _name.startswith("_"):
        globals()[_name] = _value
