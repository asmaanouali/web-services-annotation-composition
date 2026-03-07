"""
LoRA SFT Trainer for Web Service Composition.

Performs real Supervised Fine-Tuning with LoRA adapters on a causal language
model, teaching it to select optimal services based on QoS metrics and social
trust annotations.

Part of: QSRT — QoS-Driven Reinforcement Fine-Tuning with Social Trust Rewards
Phase 1: Supervised Fine-Tuning (SFT)

Architecture:
    Base Model (frozen) ──► LoRA Adapters (trainable, ~0.1% params)
                                │
    Training data ──────► SFTTrainer ──► Gradient updates on adapters only
                                │
    Saved adapter  ◄────────────┘   (small checkpoint, ~10-50 MB)

Copyright (c) 2026. All rights reserved.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List, Callable

# ---------------------------------------------------------------------------
# Lazy imports — the trainer degrades gracefully when deps are absent.
# ---------------------------------------------------------------------------
_TORCH_AVAILABLE = False
_HF_AVAILABLE = False
_PEFT_AVAILABLE = False
_DATASETS_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass

_TrainerCallback = object  # fallback
_TRANSFORMERS_AVAILABLE = False
try:
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
        TrainerCallback as _TrainerCallback,
    )
    _HF_AVAILABLE = True
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

try:
    from peft import LoraConfig, get_peft_model, PeftModel, TaskType
    _PEFT_AVAILABLE = True
except ImportError:
    pass

try:
    from datasets import Dataset
    _DATASETS_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Progress callback bridge (sends step-level updates to Flask endpoint)
# ---------------------------------------------------------------------------
class _ProgressCallback(_TrainerCallback if _TRANSFORMERS_AVAILABLE else object):
    """Transformers TrainerCallback that forwards progress to a callable."""

    def __init__(self, total_steps: int, callback: Optional[Callable] = None):
        if _TRANSFORMERS_AVAILABLE:
            super().__init__()
        self.total_steps = total_steps
        self.callback = callback

    # Called by the Trainer at each logging step
    def on_log(self, args, state, control, logs=None, **kwargs):
        if self.callback and logs:
            self.callback(
                step=state.global_step,
                total=self.total_steps,
                metrics={
                    "loss": logs.get("loss", 0),
                    "learning_rate": logs.get("learning_rate", 0),
                    "epoch": logs.get("epoch", 0),
                },
            )


# ---------------------------------------------------------------------------
# Main trainer class
# ---------------------------------------------------------------------------
class SFTLoRATrainer:
    """
    Real LoRA SFT trainer for web service composition.

    Performs actual gradient-based fine-tuning of a language model using LoRA
    (Low-Rank Adaptation), training only ~0.1 % of the total parameters.

    The trained model learns to:
        1. Parse composition requests  (inputs, outputs, QoS constraints)
        2. Evaluate candidate services (QoS metrics, social annotations)
        3. Select optimal service(s)   maximising utility
        4. Emit structured JSON output with reasoning
    """

    # Default LoRA hyper-parameters (optimised for service composition task)
    DEFAULT_LORA = {
        "r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "target_modules": [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        "bias": "none",
    }

    # Default training hyper-parameters
    DEFAULT_TRAINING = {
        "num_train_epochs": 3,
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 4,
        "learning_rate": 2e-4,
        "warmup_ratio": 0.10,
        "weight_decay": 0.01,
        "lr_scheduler_type": "cosine",
        "logging_steps": 5,
        "save_strategy": "epoch",
        "fp16": False,
        "bf16": False,
        "max_seq_length": 1024,
        "gradient_checkpointing": False,
    }

    DEFAULT_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(
        self,
        model_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        lora_config: Optional[Dict] = None,
        training_config: Optional[Dict] = None,
    ):
        self._check_dependencies()

        self.model_name = model_name or self.DEFAULT_MODEL
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "sft_adapter",
        )

        # Merge user overrides into defaults
        self.lora_config = {**self.DEFAULT_LORA, **(lora_config or {})}
        self.training_config = {**self.DEFAULT_TRAINING, **(training_config or {})}

        # Hardware detection
        self.device = self._detect_device()
        if self.device == "cuda":
            self.training_config["fp16"] = True
            self.training_config["gradient_checkpointing"] = True

        # Runtime state
        self.model = None
        self.tokenizer = None
        self.is_trained = False
        self.training_metrics: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Dependency & hardware helpers
    # ------------------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        """Return True when every required package is importable."""
        return (
            _TORCH_AVAILABLE
            and _HF_AVAILABLE
            and _PEFT_AVAILABLE
            and _DATASETS_AVAILABLE
        )

    @staticmethod
    def missing_packages() -> List[str]:
        """Return list of missing package names (empty if all present)."""
        missing = []
        if not _TORCH_AVAILABLE:
            missing.append("torch")
        if not _HF_AVAILABLE:
            missing.append("transformers")
        if not _PEFT_AVAILABLE:
            missing.append("peft")
        if not _DATASETS_AVAILABLE:
            missing.append("datasets")
        return missing

    def _check_dependencies(self):
        missing = self.missing_packages()
        if missing:
            raise ImportError(
                f"SFT training requires: {', '.join(missing)}. "
                f"Install with: pip install {' '.join(missing)}"
            )

    @staticmethod
    def _detect_device() -> str:
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            mem = torch.cuda.get_device_properties(0).total_mem / 1e9
            print(f"[SFT] GPU detected: {name} ({mem:.1f} GB)")
            return "cuda"
        print("[SFT] No GPU — using CPU (training will be slower)")
        return "cpu"

    # ------------------------------------------------------------------
    # Core training loop
    # ------------------------------------------------------------------
    def train(
        self,
        dataset: List[Dict[str, str]],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run Supervised Fine-Tuning with LoRA on *dataset*.

        Args:
            dataset: List of {"text": str} items produced by SFTDatasetBuilder
            progress_callback: Optional callable(step, total, metrics)

        Returns:
            Dictionary of training metrics.
        """
        start = time.time()

        print(f"\n{'=' * 60}")
        print("PHASE 1 — Supervised Fine-Tuning (SFT) with LoRA")
        print(f"{'=' * 60}")
        print(f"  Model           : {self.model_name}")
        print(f"  Device          : {self.device}")
        print(f"  Dataset size    : {len(dataset)} examples")
        print(f"  LoRA rank (r)   : {self.lora_config['r']}")
        print(f"  LoRA alpha      : {self.lora_config['lora_alpha']}")
        print(f"  Epochs          : {self.training_config['num_train_epochs']}")
        print(f"  Batch (eff.)    : "
              f"{self.training_config['per_device_train_batch_size']}"
              f" × {self.training_config['gradient_accumulation_steps']}")
        print(f"  LR              : {self.training_config['learning_rate']}")
        print(f"  Output dir      : {self.output_dir}")
        print(f"{'=' * 60}\n")

        # 1. Tokenizer ---------------------------------------------------
        print("[SFT 1/6] Loading tokenizer …")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        # 2. Base model ---------------------------------------------------
        print("[SFT 2/6] Loading base model …")
        dtype = (torch.float16 if self.device == "cuda" else torch.float32)
        base_model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        if self.device == "cpu":
            base_model = base_model.to("cpu")

        # 3. LoRA adapters ------------------------------------------------
        print("[SFT 3/6] Attaching LoRA adapters …")
        lora_cfg = LoraConfig(
            r=self.lora_config["r"],
            lora_alpha=self.lora_config["lora_alpha"],
            lora_dropout=self.lora_config["lora_dropout"],
            target_modules=self.lora_config["target_modules"],
            bias=self.lora_config["bias"],
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(base_model, lora_cfg)

        trainable_params, total_params = model.get_nb_trainable_parameters()
        pct = 100 * trainable_params / total_params
        print(f"  Trainable : {trainable_params:,} / {total_params:,} "
              f"({pct:.2f} %)")

        # 4. Tokenise dataset ---------------------------------------------
        print("[SFT 4/6] Tokenising dataset …")
        max_len = self.training_config["max_seq_length"]

        def _tokenise(example):
            enc = self.tokenizer(
                example["text"],
                truncation=True,
                max_length=max_len,
                padding="max_length",
            )
            enc["labels"] = enc["input_ids"].copy()
            return enc

        hf_dataset = Dataset.from_list(dataset)
        tokenised = hf_dataset.map(
            _tokenise, remove_columns=["text"], num_proc=1,
        )
        tokenised.set_format("torch")
        print(f"  Tokenised {len(tokenised)} examples (max_len={max_len})")

        # 5. Trainer setup ------------------------------------------------
        print("[SFT 5/6] Setting up Trainer …")
        os.makedirs(self.output_dir, exist_ok=True)

        training_args = TrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=self.training_config["num_train_epochs"],
            per_device_train_batch_size=self.training_config[
                "per_device_train_batch_size"],
            gradient_accumulation_steps=self.training_config[
                "gradient_accumulation_steps"],
            learning_rate=self.training_config["learning_rate"],
            warmup_ratio=self.training_config["warmup_ratio"],
            weight_decay=self.training_config["weight_decay"],
            lr_scheduler_type=self.training_config["lr_scheduler_type"],
            logging_steps=self.training_config["logging_steps"],
            save_strategy=self.training_config["save_strategy"],
            fp16=self.training_config["fp16"],
            bf16=self.training_config["bf16"],
            gradient_checkpointing=self.training_config[
                "gradient_checkpointing"],
            report_to="none",
            remove_unused_columns=False,
            dataloader_pin_memory=False,
            # Disable find_unused_parameters warning on CPU
            ddp_find_unused_parameters=False,
        )

        collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False,
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenised,
            data_collator=collator,
        )

        # Wire progress callback
        if progress_callback:
            total_steps = max(
                1,
                len(tokenised)
                // training_args.per_device_train_batch_size
                // max(training_args.gradient_accumulation_steps, 1)
                * int(training_args.num_train_epochs),
            )
            trainer.add_callback(
                _ProgressCallback(total_steps, progress_callback)
            )

        # 6. Train! -------------------------------------------------------
        print("[SFT 6/6] Training …\n")
        train_result = trainer.train()

        # Save LoRA adapter (small, ~10-50 MB)
        adapter_path = os.path.join(self.output_dir, "final_adapter")
        os.makedirs(adapter_path, exist_ok=True)
        model.save_pretrained(adapter_path)
        self.tokenizer.save_pretrained(adapter_path)

        # Save config for reproducibility
        with open(os.path.join(adapter_path, "training_config.json"), 'w') as f:
            json.dump({
                "model_name": self.model_name,
                "lora_config": self.lora_config,
                "training_config": self.training_config,
                "dataset_size": len(dataset),
                "trainable_params": trainable_params,
                "total_params": total_params,
            }, f, indent=2)

        elapsed = time.time() - start

        self.training_metrics = {
            "training_loss": train_result.training_loss,
            "total_steps": train_result.global_step,
            "epochs_completed": self.training_config["num_train_epochs"],
            "training_time_seconds": round(elapsed, 2),
            "trainable_parameters": trainable_params,
            "total_parameters": total_params,
            "parameter_efficiency": f"{pct:.2f}%",
            "dataset_size": len(dataset),
            "adapter_path": adapter_path,
            "device_used": self.device,
            "model_name": self.model_name,
        }

        self.is_trained = True
        self.model = model

        print(f"\n{'=' * 60}")
        print("SFT TRAINING COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Loss      : {train_result.training_loss:.4f}")
        print(f"  Steps     : {train_result.global_step}")
        print(f"  Time      : {elapsed:.1f} s")
        print(f"  Adapter   : {adapter_path}")
        print(f"{'=' * 60}\n")

        return self.training_metrics

    # ------------------------------------------------------------------
    # Adapter persistence
    # ------------------------------------------------------------------
    def load_adapter(self, adapter_path: Optional[str] = None) -> bool:
        """
        Load a previously saved LoRA adapter from disk.

        Returns True on success.
        """
        if adapter_path is None:
            adapter_path = os.path.join(self.output_dir, "final_adapter")

        if not os.path.exists(adapter_path):
            print(f"[SFT] No adapter at {adapter_path}")
            return False

        print(f"[SFT] Loading adapter from {adapter_path} …")

        # Read saved config to know which base model was used
        cfg_path = os.path.join(adapter_path, "training_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                saved = json.load(f)
            self.model_name = saved.get("model_name", self.model_name)
            self.training_metrics = {
                "adapter_path": adapter_path,
                "model_name": self.model_name,
                "dataset_size": saved.get("dataset_size", 0),
                "trainable_parameters": saved.get("trainable_params", 0),
                "total_parameters": saved.get("total_params", 0),
            }

        self.tokenizer = AutoTokenizer.from_pretrained(
            adapter_path, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        dtype = (torch.float16 if self.device == "cuda" else torch.float32)
        base = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        self.model = PeftModel.from_pretrained(base, adapter_path)
        if self.device == "cpu":
            self.model = self.model.to("cpu")
        self.is_trained = True

        print("[SFT] Adapter loaded ✓")
        return True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def generate(self, instruction: str,
                 max_new_tokens: int = 256) -> str:
        """
        Generate a service-selection response for *instruction*.

        Args:
            instruction: composition request text (same format as training)
            max_new_tokens: maximum generation length

        Returns:
            Generated text (expected to be JSON).
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError(
                "Model not ready. Call train() or load_adapter() first."
            )

        from services.sft_dataset import SFTDatasetBuilder

        prompt = (
            f"<|system|>\n{SFTDatasetBuilder.SYSTEM_PROMPT}\n"
            f"<|user|>\n{instruction}\n"
            f"<|assistant|>\n"
        )

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.training_config["max_seq_length"],
        )

        if self.device == "cuda":
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.3,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        # Decode only the newly generated tokens
        gen_ids = out[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)

        # Strip anything after <|end|> tag if present
        if "<|end|>" in text:
            text = text[: text.index("<|end|>")]

        return text.strip()

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------
    def get_metrics(self) -> Dict[str, Any]:
        return self.training_metrics
