# Kaggle kernels

GPU work (YOLO training for the vision track) runs on Kaggle, driven by the Kaggle CLI 2.x. Kaggle account: `mibrahimsalman022`.

- **Laptop:** run `py -3.13 -m kaggle ...`. The token is in `C:\Users\X1 Carbon\.kaggle\access_token`.
- **Cloud sessions:** run `kaggle ...`. The token comes from the `KAGGLE_API_TOKEN` environment variable.

Never commit or print the token.

Each kernel lives in its own folder with a `kernel-metadata.json` (`enable_gpu`, `enable_internet`, `is_private: true`). The workflow is:

```
kaggle kernels push -p kaggle/<name>            # upload and start the run on Kaggle
kaggle kernels status <user>/<slug>             # queued / running / complete / error
kaggle kernels output <user>/<slug> -p <dir>    # download the log and the files the run wrote to /kaggle/working
```

Datasets are attached through `dataset_sources` in the metadata (for example `bratjay/ua-detrac-orig`), so they never pass through the laptop or the cloud session.

| Kernel | Purpose | Result |
|---|---|---|
| `gpu_test/` | Checks GPU, internet and PyTorch | 12 Nov 2026: 2× Tesla T4 (15 GB each), PyTorch 2.11 sees CUDA, internet OK |
