#!/usr/bin/env python3
"""
Reviewer-facing FL adversarial showcase for Droidware.

This script runs an offline one-round federated simulation using the real
Droidware checkpoint and CSV feature layout. It compares:

1. Plain FedAvg, where every client update is averaged.
2. Droidware-style validation, where updates are evaluated, checked for
   cosine/norm anomalies, clipped if needed, and then anchored to the
   previous global model.

Outputs are written under adversarial_results/:
  - adversarial_summary.csv
  - update_validation_details.csv
  - fedavg_vs_droidware_accuracy.png
  - fedavg_vs_droidware_asr.png
  - update_validation_norms.png
  - update_validation_cosine.png
"""

import argparse
import copy
import csv
import math
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from matplotlib import pyplot as plt
from sklearn.metrics import accuracy_score, f1_score, matthews_corrcoef, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from torch import nn, optim
from torch.utils.data import DataLoader, Subset, TensorDataset


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "Droidware2025_Set2.csv"
DEFAULT_CHECKPOINT = ROOT / "global_model" / "global_model_latest.pth"
RESULTS_DIR = ROOT / "adversarial_results"


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class DeepFeedforwardNN(nn.Module):
    def __init__(self, input_dim, hidden_dims, embed_dim, pooling="avg", dropout=0.2):
        super().__init__()
        self.pooling = pooling
        effective_input_dim = input_dim * 2 if pooling == "concat" else input_dim
        layers = []
        prev_dim = effective_input_dim
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        layers.append(nn.Linear(prev_dim, embed_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        if self.pooling == "avg":
            pooled = x.mean(dim=1)
        elif self.pooling == "max":
            pooled = x.max(dim=1)[0]
        elif self.pooling == "concat":
            pooled = torch.cat([x.mean(dim=1), x.max(dim=1)[0]], dim=1)
        else:
            raise ValueError("Unsupported pooling type.")
        return self.network(pooled)


class FTTransformer(nn.Module):
    def __init__(self, input_dim, embed_dim, num_heads=4, num_layers=2, dropout=0.2):
        super().__init__()
        self.embedding = nn.Linear(input_dim, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.norm = nn.LayerNorm(embed_dim)
        self.fc = nn.Linear(embed_dim, embed_dim)

    def forward(self, x):
        x = self.embedding(x)
        x = self.transformer_encoder(x)
        x = x.mean(dim=1)
        x = self.norm(x)
        return self.fc(x)


class HybridModel(nn.Module):
    def __init__(
        self,
        input_dim,
        ff_hidden_dims,
        embed_dim,
        final_output_dim,
        pooling="avg",
        dropout=0.2,
        num_heads=4,
        num_layers=2,
        model_type=None,
    ):
        super().__init__()
        self.feedforward = DeepFeedforwardNN(input_dim, ff_hidden_dims, embed_dim, pooling, dropout)
        self.ft_transformer = FTTransformer(input_dim, embed_dim, num_heads, num_layers, dropout)
        self.combined_fc = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, final_output_dim),
        )

    def forward(self, x):
        return self.combined_fc(torch.cat([self.feedforward(x), self.ft_transformer(x)], dim=1))


def create_model(config, state_dict=None, device="cpu"):
    config = dict(config)
    config.pop("model_type", None)
    model = HybridModel(**config)
    if state_dict is not None:
        model.load_state_dict(state_dict, strict=False)
    model.to(device)
    return model


def clone_state(state_dict):
    return {key: value.detach().cpu().clone() for key, value in state_dict.items()}


def load_dataset(path, max_samples=None, seed=42):
    df = pd.read_csv(path, usecols=lambda col: col != "Sha256").dropna()
    if max_samples and max_samples < len(df):
        df = df.sample(n=max_samples, random_state=seed).reset_index(drop=True)
    label_col = df.columns[-1]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if label_col not in numeric_cols:
        features = df.select_dtypes(include=["number"]).copy()
        df[label_col] = LabelEncoder().fit_transform(df[label_col])
    else:
        features = df.drop(columns=[label_col]).copy()
    scaler = StandardScaler()
    x_np = scaler.fit_transform(features.values.astype(np.float32))
    x_np = np.expand_dims(x_np, axis=1)
    y_np = df[label_col].values.astype(np.int64)
    return TensorDataset(torch.tensor(x_np, dtype=torch.float32), torch.tensor(y_np, dtype=torch.long))


def apply_tabular_trigger(features, trigger_indices, trigger_value):
    poisoned = features.clone()
    poisoned[:, 0, trigger_indices] = trigger_value
    return poisoned


def train_client_model(
    base_state,
    config,
    dataset,
    indices,
    attack,
    malicious,
    device,
    epochs,
    batch_size,
    lr,
    trigger_indices,
    trigger_value,
    target_label,
    poison_fraction,
    gradient_scale,
    replacement_scale,
):
    model = create_model(config, base_state, device=device)
    loader = DataLoader(Subset(dataset, indices), batch_size=batch_size, shuffle=True)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    criterion = nn.CrossEntropyLoss()
    model.train()

    for _ in range(epochs):
        for features, labels in loader:
            features, labels = features.to(device), labels.to(device)
            if malicious and attack in {"backdoor", "model_replacement"}:
                poison_count = max(1, int(len(labels) * poison_fraction))
                features[:poison_count] = apply_tabular_trigger(
                    features[:poison_count], trigger_indices, trigger_value
                )
                labels[:poison_count] = target_label
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

    local_state = clone_state(model.state_dict())
    if not malicious:
        return local_state

    if attack == "gradient_scale":
        return scale_delta(base_state, local_state, gradient_scale)
    if attack == "gradient_flip":
        return scale_delta(base_state, local_state, -1.0)
    if attack == "model_replacement":
        return scale_delta(base_state, local_state, replacement_scale)
    return local_state


def flatten_state(state):
    return torch.cat([value.float().reshape(-1).cpu() for value in state.values() if torch.is_tensor(value)])


def state_delta_norm(base_state, local_state):
    total = 0.0
    for key in base_state:
        delta = local_state[key].float() - base_state[key].float()
        total += torch.sum(delta * delta).item()
    return math.sqrt(total)


def cosine_similarity(base_state, local_state):
    base_vec = flatten_state(base_state)
    local_vec = flatten_state(local_state)
    denom = torch.norm(base_vec) * torch.norm(local_vec)
    if denom.item() == 0:
        return float("nan")
    return (torch.dot(base_vec, local_vec) / denom).item()


def scale_delta(base_state, local_state, scale):
    scaled = {}
    for key in base_state:
        scaled[key] = base_state[key] + scale * (local_state[key] - base_state[key])
    return scaled


def clip_delta(base_state, local_state, max_norm):
    norm = state_delta_norm(base_state, local_state)
    if norm <= max_norm or norm == 0:
        return local_state, norm, False
    scale = max_norm / norm
    return scale_delta(base_state, local_state, scale), norm, True


def average_states(states, weights=None):
    if weights is None:
        weights = [1.0] * len(states)
    total = float(sum(weights))
    averaged = {}
    for key in states[0]:
        if not torch.is_floating_point(states[0][key]):
            averaged[key] = states[0][key].clone()
            continue
        value = torch.zeros_like(states[0][key].float())
        for state, weight in zip(states, weights):
            value += state[key].float() * (weight / total)
        averaged[key] = value
    return averaged


def anchored_weighted_average(base_state, states, weights, anchor_weight):
    return average_states([base_state] + states, [anchor_weight] + weights)


def evaluate_state(config, state, dataset, device, batch_size=128):
    model = create_model(config, state, device=device)
    model.eval()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    y_true, y_pred = [], []
    with torch.no_grad():
        for features, labels in loader:
            outputs = model(features.to(device))
            preds = torch.argmax(outputs, dim=1).cpu()
            y_true.extend(labels.numpy())
            y_pred.extend(preds.numpy())
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "mcc": matthews_corrcoef(y_true, y_pred),
    }


def backdoor_success_rate(config, state, dataset, device, trigger_indices, trigger_value, target_label):
    model = create_model(config, state, device=device)
    model.eval()
    loader = DataLoader(dataset, batch_size=128, shuffle=False)
    total, success = 0, 0
    with torch.no_grad():
        for features, labels in loader:
            mask = labels != target_label
            if mask.sum().item() == 0:
                continue
            triggered = apply_tabular_trigger(features[mask], trigger_indices, trigger_value).to(device)
            preds = torch.argmax(model(triggered), dim=1).cpu()
            success += (preds == target_label).sum().item()
            total += len(preds)
    return success / total if total else float("nan")


def droidware_filter_and_aggregate(base_state, client_states, validation_metrics, args):
    accuracies = [metrics["accuracy"] for metrics in validation_metrics]
    cosines = [cosine_similarity(base_state, state) for state in client_states]
    norms = [state_delta_norm(base_state, state) for state in client_states]

    valid = set(i for i, acc in enumerate(accuracies) if acc >= args.min_validation_accuracy)

    finite_cos = [cosines[i] for i in valid if math.isfinite(cosines[i])]
    if len(finite_cos) > 1:
        mean_cos = float(np.mean(finite_cos))
        std_cos = float(np.std(finite_cos))
        if std_cos > 0:
            valid = set(i for i in valid if abs(cosines[i] - mean_cos) <= args.cosine_lambda * std_cos)

    finite_norms = [norms[i] for i in valid if math.isfinite(norms[i])]
    if finite_norms:
        median_norm = float(np.median(finite_norms))
        mad = float(np.median(np.abs(np.array(finite_norms) - median_norm)))
        norm_bound = median_norm + args.norm_mad_lambda * (mad if mad > 0 else np.std(finite_norms))
        norm_bound = max(norm_bound, args.min_norm_bound)
    else:
        norm_bound = args.min_norm_bound

    accepted_states = []
    accepted_weights = []
    details = []
    for idx, state in enumerate(client_states):
        reason = "accepted"
        accepted = idx in valid
        clipped = False
        clipped_norm = norms[idx]
        processed_state = state
        if not accepted:
            reason = "validation_or_similarity_reject"
        elif norms[idx] > norm_bound:
            processed_state, clipped_norm, clipped = clip_delta(base_state, state, norm_bound)
            reason = "accepted_after_norm_clip"
        if accepted:
            accepted_states.append(processed_state)
            accepted_weights.append(max(accuracies[idx], 1e-6))
        details.append(
            {
                "client_id": idx,
                "accuracy": accuracies[idx],
                "f1": validation_metrics[idx]["f1"],
                "mcc": validation_metrics[idx]["mcc"],
                "cosine_similarity": cosines[idx],
                "update_norm": norms[idx],
                "norm_bound": norm_bound,
                "clipped_norm": clipped_norm,
                "accepted": accepted,
                "clipped": clipped,
                "reason": reason,
            }
        )

    if not accepted_states:
        return base_state, details

    anchor_weight = args.anchor_weight if args.anchor_weight is not None else max(np.mean(accepted_weights), 1e-6)
    aggregated = anchored_weighted_average(base_state, accepted_states, accepted_weights, anchor_weight)
    return aggregated, details


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_summary(summary_rows):
    df = pd.DataFrame(summary_rows)
    for metric, filename, ylabel in [
        ("accuracy", "fedavg_vs_droidware_accuracy.png", "Clean Accuracy"),
        ("attack_success_rate", "fedavg_vs_droidware_asr.png", "Attack Success Rate"),
        ("mcc", "fedavg_vs_droidware_mcc.png", "MCC"),
    ]:
        pivot = df.pivot(index="attack", columns="aggregation", values=metric)
        ax = pivot.plot(kind="bar", figsize=(10, 6))
        ax.set_title(f"{ylabel}: Plain FedAvg vs Droidware Validation")
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Attack")
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / filename, dpi=200)
        plt.close()


def plot_validation_details(detail_rows):
    df = pd.DataFrame(detail_rows)
    if df.empty:
        return
    for metric, filename, ylabel in [
        ("update_norm", "update_validation_norms.png", "Update Norm"),
        ("cosine_similarity", "update_validation_cosine.png", "Cosine Similarity"),
    ]:
        plt.figure(figsize=(10, 6))
        colors = df["accepted"].map({True: "tab:green", False: "tab:red"})
        plt.scatter(df["attack"], df[metric], c=colors, alpha=0.8)
        plt.title(f"Droidware Update Validation: {ylabel}")
        plt.xlabel("Attack")
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / filename, dpi=200)
        plt.close()


def run_attack(attack, checkpoint, dataset, args, device):
    config = checkpoint["config"]
    base_state = clone_state(checkpoint["model_state_dict"])

    labels = dataset.tensors[1].numpy()
    all_indices = np.arange(len(dataset))
    train_indices, test_indices = train_test_split(
        all_indices, test_size=0.3, random_state=args.seed, stratify=labels
    )
    validation_indices, test_indices = train_test_split(
        test_indices,
        test_size=0.5,
        random_state=args.seed,
        stratify=labels[test_indices],
    )
    client_splits = np.array_split(train_indices, args.clients)
    malicious_clients = set(range(args.malicious_clients))
    trigger_indices = list(range(min(args.trigger_features, dataset.tensors[0].shape[2])))

    client_states = []
    for client_id, indices in enumerate(client_splits):
        state = train_client_model(
            base_state=base_state,
            config=config,
            dataset=dataset,
            indices=indices.tolist(),
            attack=attack,
            malicious=client_id in malicious_clients,
            device=device,
            epochs=args.local_epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            trigger_indices=trigger_indices,
            trigger_value=args.trigger_value,
            target_label=args.target_label,
            poison_fraction=args.poison_fraction,
            gradient_scale=args.gradient_scale,
            replacement_scale=args.replacement_scale,
        )
        client_states.append(state)

    validation_dataset = Subset(dataset, validation_indices.tolist())
    test_dataset = Subset(dataset, test_indices.tolist())
    validation_metrics = [
        evaluate_state(config, state, validation_dataset, device=device) for state in client_states
    ]

    fedavg_state = average_states(client_states)
    droidware_state, details = droidware_filter_and_aggregate(
        base_state, client_states, validation_metrics, args
    )

    summary_rows = []
    for aggregation, state in [("FedAvg", fedavg_state), ("Droidware", droidware_state)]:
        metrics = evaluate_state(config, state, test_dataset, device=device)
        asr = (
            backdoor_success_rate(
                config,
                state,
                test_dataset,
                device,
                trigger_indices,
                args.trigger_value,
                args.target_label,
            )
            if attack in {"backdoor", "model_replacement"}
            else float("nan")
        )
        summary_rows.append(
            {
                "attack": attack,
                "aggregation": aggregation,
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "mcc": metrics["mcc"],
                "attack_success_rate": asr,
                "accepted_updates": sum(1 for row in details if row["accepted"]),
                "total_updates": len(details),
            }
        )

    for row in details:
        row["attack"] = attack
        row["malicious"] = row["client_id"] in malicious_clients
    return summary_rows, details


def parse_args():
    parser = argparse.ArgumentParser(description="Droidware FL adversarial showcase")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--max-samples", type=int, default=3000)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--malicious-clients", type=int, default=1)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--attacks",
        nargs="+",
        default=["backdoor", "gradient_scale", "gradient_flip", "model_replacement"],
        choices=["backdoor", "gradient_scale", "gradient_flip", "model_replacement"],
    )
    parser.add_argument("--target-label", type=int, default=0)
    parser.add_argument("--trigger-features", type=int, default=5)
    parser.add_argument("--trigger-value", type=float, default=5.0)
    parser.add_argument("--poison-fraction", type=float, default=0.5)
    parser.add_argument("--gradient-scale", type=float, default=10.0)
    parser.add_argument("--replacement-scale", type=float, default=15.0)
    parser.add_argument("--min-validation-accuracy", type=float, default=0.10)
    parser.add_argument("--cosine-lambda", type=float, default=2.0)
    parser.add_argument("--norm-mad-lambda", type=float, default=2.0)
    parser.add_argument("--min-norm-bound", type=float, default=0.05)
    parser.add_argument("--anchor-weight", type=float, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(args.seed)
    RESULTS_DIR.mkdir(exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    print(f"Loading checkpoint: {args.checkpoint}")
    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    print(f"Loading dataset: {args.dataset}")
    dataset = load_dataset(args.dataset, max_samples=args.max_samples, seed=args.seed)

    all_summary_rows = []
    all_detail_rows = []
    for attack in args.attacks:
        print(f"Running attack: {attack}")
        summary_rows, detail_rows = run_attack(attack, checkpoint, dataset, args, device)
        all_summary_rows.extend(summary_rows)
        all_detail_rows.extend(detail_rows)

    summary_fields = [
        "attack",
        "aggregation",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "mcc",
        "attack_success_rate",
        "accepted_updates",
        "total_updates",
    ]
    detail_fields = [
        "attack",
        "client_id",
        "malicious",
        "accuracy",
        "f1",
        "mcc",
        "cosine_similarity",
        "update_norm",
        "norm_bound",
        "clipped_norm",
        "accepted",
        "clipped",
        "reason",
    ]
    write_csv(RESULTS_DIR / "adversarial_summary.csv", all_summary_rows, summary_fields)
    write_csv(RESULTS_DIR / "update_validation_details.csv", all_detail_rows, detail_fields)
    plot_summary(all_summary_rows)
    plot_validation_details(all_detail_rows)
    print(f"Saved outputs to: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
