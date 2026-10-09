# Telemetry RCA Language Model (Fine-Tuned Qwen2-7B)

This directory stores the fine-tuned **Qwen2 7.6B Causal Language Model** used for Root Cause Analysis (RCA) and automated runbook generation in the AIOps platform.

---

## Model Specifications
* **Base Architecture:** `Qwen2ForCausalLM`
* **Parameters:** ~7.6 Billion (28 layers, hidden size 3584)
* **Precision:** `bfloat16`
* **Prompt Format:** ChatML (`<|im_start|>system ... <|im_end|>\n<|im_start|>user ... <|im_end|>\n<|im_start|>assistant\n`)
* **Task:** Kubernetes telemetry anomaly correlation, root cause diagnosis, and SRE incident mitigation runbook generation.

---

## Weights Storage & Download
Due to GitHub's file size limits, the 4 model weight shards (`*.safetensors`, totaling ~15.2 GB) are hosted on Google Drive:

* **Google Drive Link:** [Download Model Weights](https://drive.google.com/drive/folders/14zOGPO9NwVszn7jAzoda6fTAsCKraxRo?usp=sharing)

### Automated Download via gdown
To pull the weights automatically into this directory, run:
```powershell
python -m gdown --folder "https://drive.google.com/drive/folders/14zOGPO9NwVszn7jAzoda6fTAsCKraxRo?usp=sharing"
```

The model files will be downloaded as:
* `model-00001-of-00004.safetensors` (4.88 GB)
* `model-00002-of-00004.safetensors` (4.93 GB)
* `model-00003-of-00004.safetensors` (4.33 GB)
* `model-00004-of-00004.safetensors` (1.09 GB)
