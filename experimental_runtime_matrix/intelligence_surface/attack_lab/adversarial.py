#!/usr/bin/env python3
"""
=============================================================================
FL Attack Simulation Experiment — Concern #8 Response
=============================================================================
Simulates all three FL-specific attacks in a SINGLE PROCESS.
No server, no client, no network, no TLS required.

Attacks evaluated:
  1. Backdoor Attack       — trigger pattern injected into training features
  2. Gradient Manipulation — malicious update scaled to dominate FedAvg
  3. Model Replacement     — boosted malicious model replaces global model

Architecture mirrors your server26.py:
  - HybridModel (DeepFeedforwardNN + FTTransformer)
  - Weighted FedAvg aggregation (same formula as server26.py lines 1872–1892)
  - Same metrics: Accuracy, Precision, Recall, F1, MCC, Markedness, Youden's J, FMI

Dataset: Droidware_Android_Malware_Dataset.csv (your uploaded file)
=============================================================================
"""

import copy
import math
import warnings
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, Subset
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, matthews_corrcoef, confusion_matrix
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATASET_PATH   = "Droidware_Android_Malware_Dataset.csv"
EPOCHS         = 5           # local training epochs per client
BATCH_SIZE     = 64
LR             = 1e-3
N_HONEST       = 1           # honest clients
N_MALICIOUS    = 1           # malicious clients (1 is enough to show impact)
SCALE_FACTOR   = 10.0        # gradient manipulation amplification
POISON_RATE    = 0.30        # fraction of samples to poison for backdoor
TARGET_CLASS   = 0           # backdoor target label
TRIGGER_DIM    = 5           # number of features overwritten by trigger
DEVICE         = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ─────────────────────────────────────────────
# MODEL DEFINITIONS (from server26.py / client12.py)
# ─────────────────────────────────────────────

class DeepFeedforwardNN(nn.Module):
    def __init__(self, input_dim, hidden_dims, embed_dim, pooling="avg", dropout=0.2):
        super().__init__()
        self.pooling = pooling
        eff = input_dim * 2 if pooling == "concat" else input_dim
        layers, prev = [], eff
        for h in hidden_dims:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, embed_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        if self.pooling == "avg":
            x = x.mean(dim=1)
        elif self.pooling == "max":
            x = x.max(dim=1)[0]
        elif self.pooling == "concat":
            x = torch.cat([x.mean(dim=1), x.max(dim=1)[0]], dim=1)
        return self.network(x)


class FTTransformer(nn.Module):
    def __init__(self, input_dim, embed_dim, num_heads=4, num_layers=2, dropout=0.2):
        super().__init__()
        self.embedding = nn.Linear(input_dim, embed_dim)
        enc = nn.TransformerEncoderLayer(
            d_model=embed_dim, nhead=num_heads, dropout=dropout, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(enc, num_layers=num_layers)
        self.norm = nn.LayerNorm(embed_dim)
        self.fc   = nn.Linear(embed_dim, embed_dim)

    def forward(self, x):
        x = self.embedding(x)
        x = self.transformer_encoder(x)
        x = self.norm(x.mean(dim=1))
        return self.fc(x)


class HybridModel(nn.Module):
    def __init__(self, input_dim, ff_hidden_dims, embed_dim, final_output_dim,
                 pooling="avg", dropout=0.2, num_heads=4, num_layers=2):
        super().__init__()
        self.feedforward  = DeepFeedforwardNN(input_dim, ff_hidden_dims, embed_dim, pooling, dropout)
        self.ft_transformer = FTTransformer(input_dim, embed_dim, num_heads, num_layers, dropout)
        self.combined_fc  = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(embed_dim, final_output_dim)
        )

    def forward(self, x):
        return self.combined_fc(torch.cat([self.feedforward(x), self.ft_transformer(x)], dim=1))


def build_model(input_dim, num_classes):
    return HybridModel(
        input_dim=input_dim,
        ff_hidden_dims=[128, 64],
        embed_dim=32,
        final_output_dim=num_classes,
        pooling="avg",
        dropout=0.2,
        num_heads=4,
        num_layers=2
    )

# ─────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────

class DroidwareDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        X = np.expand_dims(X, axis=1)          # (N, 1, F) — matches client12.py
        self.features = torch.tensor(X, dtype=torch.float32)
        self.labels   = torch.tensor(y, dtype=torch.long)

    def __len__(self):  return len(self.labels)
    def __getitem__(self, i): return self.features[i], self.labels[i]


def load_dataset(path):
    df = pd.read_csv(path, usecols=lambda c: c not in ["Sha256"])
    df.dropna(inplace=True)
    label_col = df.columns[-1]
    le = LabelEncoder()
    df[label_col] = le.fit_transform(df[label_col])
    X = df.drop(columns=[label_col]).select_dtypes(include=["number"]).values.astype(np.float32)
    y = df[label_col].values
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    return X, y, len(np.unique(y))

# ─────────────────────────────────────────────
# METRICS  (same as server26.py compute_all_metrics)
# ─────────────────────────────────────────────

def compute_all_metrics(y_true, y_pred):
    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
    rec  = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f1   = f1_score(y_true, y_pred, average="macro", zero_division=0)
    mcc  = matthews_corrcoef(y_true, y_pred)
    cm   = confusion_matrix(y_true, y_pred)
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        npv         = tn / (tn + fn) if (tn + fn) > 0 else 0
        spec        = tn / (tn + fp) if (tn + fp) > 0 else 0
        markedness  = prec + npv - 1
        youdens_j   = rec + spec - 1
    else:
        markedness = youdens_j = float("nan")
    fmi = math.sqrt(prec * rec) if prec >= 0 and rec >= 0 else 0
    return dict(accuracy=acc, precision=prec, recall=rec, f1=f1,
                mcc=mcc, markedness=markedness, youdens_j=youdens_j, fmi=fmi)

# ─────────────────────────────────────────────
# TRIGGER HELPER  (for backdoor + model replacement)
# ─────────────────────────────────────────────

def add_trigger(x: torch.Tensor) -> torch.Tensor:
    """Overwrite the last TRIGGER_DIM features with a constant value of 1.0."""
    x = x.clone()
    x[:, :, -TRIGGER_DIM:] = 1.0
    return x

# ─────────────────────────────────────────────
# LOCAL TRAINING  (honest — same logic as client12.py train_local_model)
# ─────────────────────────────────────────────

def train_honest(model, loader):
    model = copy.deepcopy(model).to(DEVICE)
    opt   = optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    sch   = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    crit  = nn.CrossEntropyLoss()
    model.train()
    for _ in range(EPOCHS):
        for X, y in loader:
            X, y = X.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            loss = crit(model(X), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sch.step()
    return model

# ─────────────────────────────────────────────
# ATTACK 1: BACKDOOR
# ─────────────────────────────────────────────

def train_backdoor(global_model, loader):
    """
    Malicious client poisons POISON_RATE fraction of each batch:
      - adds trigger pattern to features
      - flips label to TARGET_CLASS
    Reference: Gu et al., BadNets (2017)
    """
    model = copy.deepcopy(global_model).to(DEVICE)
    opt   = optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    crit  = nn.CrossEntropyLoss()
    model.train()
    for _ in range(EPOCHS):
        for X, y in loader:
            X, y = X.to(DEVICE), y.to(DEVICE)
            # Poison a fraction
            mask = torch.rand(len(X)) < POISON_RATE
            X[mask] = add_trigger(X[mask])
            y[mask] = TARGET_CLASS
            opt.zero_grad()
            loss = crit(model(X), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
    return model

# ─────────────────────────────────────────────
# ATTACK 2: GRADIENT MANIPULATION  ("Little Is Enough")
# ─────────────────────────────────────────────

def train_gradient_manipulation(global_model, loader):
    """
    Trains honestly, then scales the update (W_local - W_global) by SCALE_FACTOR.
    Reference: Baruch et al., A Little Is Enough (NeurIPS 2019)
    """
    global_state = copy.deepcopy(global_model.state_dict())
    model = copy.deepcopy(global_model).to(DEVICE)
    opt   = optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    crit  = nn.CrossEntropyLoss()
    model.train()
    for _ in range(EPOCHS):
        for X, y in loader:
            X, y = X.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            loss = crit(model(X), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

    # Amplify the update
    manipulated_state = {}
    local_state = model.state_dict()
    for k in global_state:
        delta = local_state[k].cpu() - global_state[k].cpu()
        manipulated_state[k] = global_state[k].cpu() + SCALE_FACTOR * delta

    model.load_state_dict(manipulated_state)
    return model

# ─────────────────────────────────────────────
# ATTACK 3: MODEL REPLACEMENT
# ─────────────────────────────────────────────

def train_model_replacement(global_model, loader, n_total_clients):
    """
    Trains a fully backdoored model and boosts its update to survive FedAvg averaging.
    boost = n_clients / n_malicious  ensures replacement survives averaging.
    Reference: Bhagoji et al., Adversarial Lens (ICML 2019)
    """
    n_malicious   = N_MALICIOUS
    boost         = n_total_clients / n_malicious   # survive FedAvg

    global_state  = copy.deepcopy(global_model.state_dict())
    model         = copy.deepcopy(global_model).to(DEVICE)
    opt           = optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    crit          = nn.CrossEntropyLoss()
    model.train()
    for _ in range(EPOCHS):
        for X, y in loader:
            X, y = X.to(DEVICE), y.to(DEVICE)
            # All samples get trigger + forced to TARGET_CLASS
            X = add_trigger(X)
            y = torch.full_like(y, TARGET_CLASS)
            opt.zero_grad()
            loss = crit(model(X), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

    # Boosted replacement: W_out = boost*(W_mal - W_global) + W_global
    replacement_state = {}
    local_state = model.state_dict()
    for k in global_state:
        delta = local_state[k].cpu() - global_state[k].cpu()
        replacement_state[k] = global_state[k].cpu() + boost * delta

    model.load_state_dict(replacement_state)
    return model

# ─────────────────────────────────────────────
# FEDAVG AGGREGATION  (mirrors server26.py lines 1872–1892)
# ─────────────────────────────────────────────

def fedavg(global_model, client_models, weights=None):
    """
    Weighted FedAvg: same formula as server26.py
      aggregated[k] = sum_i( weight_i / total_weight * param_i )
    """
    if weights is None:
        weights = [1.0] * len(client_models)

    total_weight  = sum(weights)
    global_state  = copy.deepcopy(global_model.state_dict())
    aggregated    = {k: torch.zeros_like(v, dtype=torch.float32)
                     for k, v in global_state.items()}

    for cm, w in zip(client_models, weights):
        for k, v in cm.state_dict().items():
            aggregated[k] += v.cpu().float() * (w / total_weight)

    new_model = copy.deepcopy(global_model)
    new_model.load_state_dict(aggregated)
    return new_model

# ─────────────────────────────────────────────
# EVALUATION
# ─────────────────────────────────────────────

def evaluate(model, loader):
    model.eval().to(DEVICE)
    y_true, y_pred = [], []
    with torch.no_grad():
        for X, y in loader:
            X = X.to(DEVICE)
            preds = model(X).argmax(dim=1).cpu().numpy()
            y_pred.extend(preds)
            y_true.extend(y.numpy())
    return compute_all_metrics(np.array(y_true), np.array(y_pred))


def attack_success_rate(model, loader):
    """ASR: % of clean (non-triggered) samples that get classified as TARGET_CLASS after trigger injection."""
    model.eval().to(DEVICE)
    triggered, target_count = 0, 0
    with torch.no_grad():
        for X, y in loader:
            X = add_trigger(X).to(DEVICE)
            preds = model(X).argmax(dim=1).cpu()
            target_count += (preds == TARGET_CLASS).sum().item()
            triggered    += len(preds)
    return target_count / triggered if triggered > 0 else 0.0

# ─────────────────────────────────────────────
# MAIN EXPERIMENT
# ─────────────────────────────────────────────

def run_experiment(scenario_name, attack_fn, attack_fn_kwargs=None):
    print(f"\n{'='*60}")
    print(f"  SCENARIO: {scenario_name}")
    print(f"{'='*60}")

    # ── Data ──────────────────────────────────────────────────────
    X, y, num_classes = load_dataset(DATASET_PATH)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Split train into honest + malicious halves
    n = len(X_train)
    honest_idx    = np.arange(0,   n // 2)
    malicious_idx = np.arange(n // 2, n)

    honest_ds    = DroidwareDataset(X_train[honest_idx],    y_train[honest_idx])
    malicious_ds = DroidwareDataset(X_train[malicious_idx], y_train[malicious_idx])
    test_ds      = DroidwareDataset(X_test, y_test)

    honest_loader    = DataLoader(honest_ds,    batch_size=BATCH_SIZE, shuffle=True)
    malicious_loader = DataLoader(malicious_ds, batch_size=BATCH_SIZE, shuffle=True)
    test_loader      = DataLoader(test_ds,      batch_size=BATCH_SIZE, shuffle=False)

    input_dim = X_train.shape[1]

    # ── Global model ──────────────────────────────────────────────
    global_model = build_model(input_dim, num_classes)

    # ── Baseline: clean FedAvg (no attack) ──────────────────────
    honest_update   = train_honest(global_model, honest_loader)
    clean_aggregated = fedavg(global_model, [honest_update])
    baseline_metrics = evaluate(clean_aggregated, test_loader)
    baseline_asr     = attack_success_rate(clean_aggregated, test_loader)

    print(f"\n[BASELINE — No Attack]")
    print(f"  Main Task Accuracy : {baseline_metrics['accuracy']*100:.2f}%")
    print(f"  F1 Score           : {baseline_metrics['f1']*100:.2f}%")
    print(f"  MCC                : {baseline_metrics['mcc']:.4f}")
    print(f"  ASR (trigger→{TARGET_CLASS})  : {baseline_asr*100:.2f}%")

    # ── Attack ────────────────────────────────────────────────────
    kwargs = attack_fn_kwargs or {}
    malicious_update = attack_fn(global_model, malicious_loader, **kwargs)

    # FedAvg with 1 honest + 1 malicious client (equal weight)
    attacked_model   = fedavg(global_model,
                               [honest_update, malicious_update],
                               weights=[1.0, 1.0])

    attack_metrics   = evaluate(attacked_model, test_loader)
    attack_asr       = attack_success_rate(attacked_model, test_loader)

    print(f"\n[UNDER ATTACK]")
    print(f"  Main Task Accuracy : {attack_metrics['accuracy']*100:.2f}%")
    print(f"  F1 Score           : {attack_metrics['f1']*100:.2f}%")
    print(f"  MCC                : {attack_metrics['mcc']:.4f}")
    print(f"  ASR (trigger→{TARGET_CLASS})  : {attack_asr*100:.2f}%")

    acc_drop = (baseline_metrics['accuracy'] - attack_metrics['accuracy']) * 100
    asr_gain = (attack_asr - baseline_asr) * 100
    print(f"\n[IMPACT]")
    print(f"  Accuracy Drop : {acc_drop:+.2f}%")
    print(f"  ASR Gain      : {asr_gain:+.2f}%")

    return {
        "scenario"          : scenario_name,
        "baseline_accuracy" : baseline_metrics["accuracy"],
        "baseline_asr"      : baseline_asr,
        "attack_accuracy"   : attack_metrics["accuracy"],
        "attack_asr"        : attack_asr,
        "accuracy_drop"     : acc_drop,
        "asr_gain"          : asr_gain,
        "attack_f1"         : attack_metrics["f1"],
        "attack_mcc"        : attack_metrics["mcc"],
        "attack_markedness" : attack_metrics["markedness"],
        "attack_youdens_j"  : attack_metrics["youdens_j"],
    }


# ─────────────────────────────────────────────
# PRINT SUMMARY TABLE
# ─────────────────────────────────────────────

def print_summary(results):
    print(f"\n\n{'='*80}")
    print("  SUMMARY TABLE — Reviewer Concern #8: Stronger FL-Specific Attacks")
    print(f"{'='*80}")
    header = f"{'Attack':<30} {'Main Acc':>10} {'Acc Drop':>10} {'ASR':>10} {'F1':>8} {'MCC':>8}"
    print(header)
    print("-" * 80)
    for r in results:
        print(
            f"{r['scenario']:<30}"
            f"{r['attack_accuracy']*100:>9.2f}%"
            f"{r['accuracy_drop']:>+10.2f}%"
            f"{r['attack_asr']*100:>9.2f}%"
            f"{r['attack_f1']*100:>7.2f}%"
            f"{r['attack_mcc']:>8.4f}"
        )
    print(f"{'='*80}")
    print("\nMetrics legend:")
    print("  Main Acc  — global model accuracy on clean test set after aggregation")
    print("  Acc Drop  — accuracy change vs. no-attack baseline (negative = degraded)")
    print(f"  ASR       — Attack Success Rate: % of triggered inputs classified as class {TARGET_CLASS}")
    print("  F1 / MCC  — macro F1 and Matthews Correlation Coefficient")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\nFL Attack Experiment — Concern #8 (Single Process, No Network Required)")
    print(f"Device: {DEVICE} | Dataset: {DATASET_PATH}")
    print(f"Config: epochs={EPOCHS}, batch={BATCH_SIZE}, lr={LR}, "
          f"poison_rate={POISON_RATE}, scale_factor={SCALE_FACTOR}")

    total_clients = N_HONEST + N_MALICIOUS

    results = []

    # ── Backdoor Attack ──────────────────────────────────────────
    results.append(run_experiment(
        scenario_name  = "Backdoor (BadNets)",
        attack_fn      = train_backdoor,
    ))

    # ── Gradient Manipulation ────────────────────────────────────
    results.append(run_experiment(
        scenario_name  = f"Gradient Manip. (x{SCALE_FACTOR})",
        attack_fn      = train_gradient_manipulation,
    ))

    # ── Model Replacement ────────────────────────────────────────
    results.append(run_experiment(
        scenario_name  = f"Model Replacement (boost={total_clients})",
        attack_fn      = train_model_replacement,
        attack_fn_kwargs = {"n_total_clients": total_clients},
    ))

    print_summary(results)

    # ── Save results to CSV ──────────────────────────────────────
    import csv
    output_csv = "attack_experiment_results.csv"
    fieldnames = list(results[0].keys())
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to: {output_csv}")