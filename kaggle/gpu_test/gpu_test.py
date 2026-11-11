import subprocess, sys
print(sys.version)
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"], capture_output=True, text=True).stdout)
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.device_count())
import urllib.request
print("internet", urllib.request.urlopen("https://pypi.org", timeout=10).status)
