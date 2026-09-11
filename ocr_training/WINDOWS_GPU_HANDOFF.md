# Windows/RTX 5090 training handoff

Everything needed to fine-tune the "orange kid" level-badge digit recognizer
on a GPU machine, picking up from where the CPU run on the Mac left off
(killed deliberately - it was tracking a ~4 hour ETA at 2.81 samples/sec on
CPU; see the ips/eta numbers logged before it was stopped).

## What's already here (tracked in git)

- `generate_orange_kid_data.py` - synthesizes the training dataset by
  rendering random digit strings in the actual extracted game font over
  backgrounds approximating the real badge crops.
- `orange_kid_rec.yaml` - the PaddleX training config (currently set for
  CPU - see step 4 below).
- `train.py` - driver script (`paddlex.engine.Engine`, which PaddleX itself
  doesn't ship a runnable entry point for outside its CLI's inference-only
  `--pipeline` path).

## What's NOT here and needs transferring

**`data/fonts/orange_kid.ttf`** - the game's own custom font, extracted
from `data.unity3d` via UnityPy. It's gitignored on purpose (copyrighted
game asset, kept under the same `data/` boundary as screenshots, not
committed to tracked source) - so it won't come across via git and needs
one of:

- **Copy it directly** from this Mac (`data/fonts/orange_kid.ttf`, 38KB) -
  simplest if you have any file-transfer path between the two machines.
- **Re-extract it** on the Windows box from your own copy of the game, if
  you'd rather not transfer the file:

  ```python
  # pip install UnityPy first
  import UnityPy
  # path will differ on Windows - find the game's own Contents/Resources/Data
  # equivalent (typically <install_dir>\Foundation Galactic Frontier_Data\data.unity3d
  # or similar - check the game's install folder for a data.unity3d file)
  env = UnityPy.load(r"C:\path\to\data.unity3d")
  for o in env.objects:
      if str(o.type) == "128":  # Font
          d = o.read()
          if d.m_Name == "orange kid":
              with open("orange_kid.ttf", "wb") as f:
                  f.write(bytes(d.m_FontData))
  ```

  Put the resulting file at `data/fonts/orange_kid.ttf` relative to the
  repo root (same relative path `generate_orange_kid_data.py` expects).

## Setup steps

1. **Python version**: `paddlepaddle` (as of 3.3.1) ships wheels for
   Python 3.9-3.13 only - confirmed no 3.14 wheel exists. Use whatever
   compatible version you have; a dedicated venv isn't strictly required
   on Windows the way it was on the Mac (where the main project venv was
   3.14), but keeping OCR training tooling in its own venv is still good
   hygiene given how many extra dependencies it pulls in.

2. **Install paddlepaddle-gpu** (NOT plain `paddlepaddle` - that's the
   CPU-only build that was used for the Mac run):

   ```
   pip install paddlepaddle-gpu
   ```

   Follow PaddlePaddle's own install-matrix for the exact CUDA/cuDNN
   version pairing your driver supports - this varies by paddlepaddle
   release and wasn't verified here (no GPU available on the Mac to test
   against). Verify with:

   ```
   python -c "import paddle; paddle.utils.run_check()"
   ```

   It should report a GPU device, not "works well on 1 CPU" like the Mac did.

3. **Install paddleocr + matplotlib**:

   ```
   pip install paddleocr matplotlib
   ```

4. **Install the PaddleOCR training plugin**:

   ```
   paddlex --install PaddleOCR -y
   ```

   This clones the actual PaddleOCR repo (with its model configs) into
   the paddlex package directory. **Three bugs were hit doing this on the
   Mac - all in PaddleX's own packaging, not Mac-specific, so expect to
   hit them here too:**

   - **Missing `repos` directory crashes the installer before it creates
     the directory itself.** Fix: create it first.

     ```
     mkdir <path-to-site-packages>\paddlex\repo_manager\repos
     ```

     (Find the exact path with `python -c "import paddlex, os; print(os.path.dirname(paddlex.__file__))"`.)

   - **`matplotlib` isn't pulled in automatically** even though PaddleX's
     dataset-analysis step needs it (already covered by step 3 above, but
     if you install PaddleOCR plugin before matplotlib, you'll see a
     `DependencyError` mentioning it).

   - **Missing model config mapping**: after installing, training will
     fail with `UnsupportedParamError: 'en_PP-OCRv4_mobile_rec' is not a
     registered model name`, then (after a fix attempt) a
     `FileNotFoundError` for
     `paddlex/repo_apis/PaddleOCR_api/configs/en_PP-OCRv4_mobile_rec.yaml`.
     PaddleX expects a flat `configs/` directory here that never gets
     populated from the actual cloned PaddleOCR repo. Fix: copy it over
     manually (extension changes from `.yml` to `.yaml`):

     ```
     mkdir <site-packages>\paddlex\repo_apis\PaddleOCR_api\configs
     copy <site-packages>\paddlex\repo_manager\repos\PaddleOCR\configs\rec\PP-OCRv4\en_PP-OCRv4_mobile_rec.yml ^
          <site-packages>\paddlex\repo_apis\PaddleOCR_api\configs\en_PP-OCRv4_mobile_rec.yaml
     ```

5. **Generate the dataset** (from the `ocr_training/` directory, main
   project venv is fine for this - it's pure PIL, no paddle dependency):

   ```
   python generate_orange_kid_data.py
   ```

   Produces `orange_kid_dataset/` with 2000 train + 200 val synthetic
   samples. Bump `n_train`/`n_val` in the script if you want more, given a
   GPU makes larger datasets much more affordable.

6. **Edit `orange_kid_rec.yaml`**: change `Global.device` from `cpu` to
   `gpu:0`. Consider also raising `Train.batch_size` (currently 32, tuned
   for CPU) - a 5090 can push this much higher for better GPU utilization
   on a model this small; there's no established right number here, worth
   just trying 128 or 256 and watching GPU memory/throughput.

7. **Run training**:

   ```
   python train.py -c orange_kid_rec.yaml
   ```

   Progress logs the same way it did on the Mac - watch for
   `epoch: [N/20], ... acc: ..., ips: ... samples/s, eta: ...` lines. On
   the Mac's CPU this measured 2.81 samples/sec with a ~4 hour ETA; a 5090
   should bring this down to low minutes for the full run (see the
   conversation this note came from for the reasoning - GPUs give
   outsized speedups on small CRNN-style models like this, though the
   realized gain may land a bit under the raw compute ratio once
   CPU-side data loading/augmentation becomes the new bottleneck).

## After training

`output/best_accuracy/` will hold the fine-tuned weights. Evaluate against
real captured crops (not just the synthetic val set) before treating this
as done - synthetic-data accuracy doesn't guarantee real-world accuracy,
and validating against genuine screen captures was always the plan (see
the pipeline scoping discussion this note is a continuation of).
