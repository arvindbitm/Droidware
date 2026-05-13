#!/usr/bin/env python3
import argparse
import csv
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from matplotlib import pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "Droidware2025_Set2.csv"
DEFAULT_GLOBAL_MODEL = ROOT / "global_model" / "global_model_latest.pth"
DEFAULT_BASE_MODEL = ROOT / "best_hybrid_model_state.pth"
DEFAULT_OUTPUT_ROOT = ROOT / "model_evaluation_outputs"


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


def resolve_model_path(model_source, model_path):
    if model_source in {"global", "present", "current"}:
        return DEFAULT_GLOBAL_MODEL
    if model_source == "best":
        return DEFAULT_BASE_MODEL
    if model_source == "path":
        if not model_path:
            raise ValueError("--model-path is required when --model-source path is used.")
        return Path(model_path)
    raise ValueError(f"Unsupported model source: {model_source}")


def load_dataset(path):
    df = pd.read_csv(path, usecols=lambda col: col != "Sha256").dropna().reset_index(drop=True)
    label_col = df.columns[-1]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if label_col not in numeric_cols:
        features = df.select_dtypes(include=["number"]).copy()
        labels = LabelEncoder().fit_transform(df[label_col])
    else:
        features = df.drop(columns=[label_col]).copy()
        labels = df[label_col].values.astype(np.int64)

    scaler = StandardScaler()
    x_np = scaler.fit_transform(features.values.astype(np.float32))
    x_np = np.expand_dims(x_np, axis=1)
    dataset = TensorDataset(
        torch.tensor(x_np, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
    )
    return dataset, labels


def load_model(checkpoint_path, device):
    checkpoint = torch.load(checkpoint_path, map_location=device)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint or "config" not in checkpoint:
        raise ValueError(f"Unsupported checkpoint format in {checkpoint_path}")

    config = dict(checkpoint["config"])
    config.pop("model_type", None)
    model = HybridModel(**config)
    model.load_state_dict(checkpoint["model_state_dict"], strict=False)
    model.to(device)
    model.eval()
    return model, checkpoint.get("config", {})


def evaluate_model(model, dataset, device):
    loader = DataLoader(dataset, batch_size=64, shuffle=False)
    y_true = []
    y_pred = []
    y_score = []

    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            logits = model(features)
            probs = torch.softmax(logits, dim=1)
            preds = torch.argmax(probs, dim=1)
            y_true.extend(labels.cpu().numpy())
            y_pred.extend(preds.cpu().numpy())
            if probs.shape[1] == 2:
                y_score.extend(probs[:, 1].cpu().numpy())
            else:
                y_score.extend(torch.max(probs, dim=1).values.cpu().numpy())

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    y_score = np.array(y_score)
    return y_true, y_pred, y_score


def write_summary_csv(output_dir, model_path, dataset_path, config, metrics):
    summary_path = output_dir / "metrics_summary.csv"
    rows = [
        ("model_path", str(model_path)),
        ("dataset_path", str(dataset_path)),
        ("model_type", config.get("model_type", "HybridModel")),
        ("input_dim", config.get("input_dim")),
        ("final_output_dim", config.get("final_output_dim")),
    ]
    rows.extend((key, value) for key, value in metrics.items())
    with open(summary_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def write_predictions_csv(output_dir, y_true, y_pred, y_score):
    path = output_dir / "prediction_scores.csv"
    df = pd.DataFrame(
        {
            "sample_index": np.arange(len(y_true)),
            "y_true": y_true,
            "y_pred": y_pred,
            "positive_score": y_score,
        }
    )
    df.to_csv(path, index=False)


def write_confusion_csv(output_dir, cm):
    path = output_dir / "confusion_matrix.csv"
    pd.DataFrame(cm).to_csv(path, index=False)


def write_roc_csv(output_dir, fpr, tpr, thresholds):
    path = output_dir / "roc_curve_points.csv"
    pd.DataFrame(
        {
            "fpr": fpr,
            "tpr": tpr,
            "threshold": thresholds,
        }
    ).to_csv(path, index=False)


def plot_confusion_matrix(output_dir, cm):
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(cm, cmap="Blues")
    plt.colorbar(image, ax=ax)
    ax.set_title("Confusion Matrix")
    ax.set_xlabel("Predicted Label")
    ax.set_ylabel("True Label")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix.png", dpi=200)
    plt.close(fig)


def plot_roc(output_dir, fpr, tpr, roc_auc):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(fpr, tpr, label=f"ROC curve (AUC = {roc_auc:.4f})", linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Random baseline")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "roc_curve.png", dpi=200)
    plt.close(fig)


def plot_score_histogram(output_dir, y_score, y_true):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(y_score[y_true == 0], bins=30, alpha=0.6, label="Class 0")
    ax.hist(y_score[y_true == 1], bins=30, alpha=0.6, label="Class 1")
    ax.set_xlabel("Positive Class Score")
    ax.set_ylabel("Count")
    ax.set_title("Prediction Score Distribution")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "score_distribution.png", dpi=200)
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate CSVs and graphs, including ROC and AUC, for the global/current Droidware model."
    )
    parser.add_argument(
        "--model-source",
        default="global",
        choices=["global", "present", "current", "best", "path"],
        help="Choose the model checkpoint source.",
    )
    parser.add_argument("--model-path", help="Used only when --model-source path is selected.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--output-name", help="Optional fixed output folder name.")
    return parser.parse_args()


def main():
    args = parse_args()
    model_path = resolve_model_path(args.model_source, args.model_path)
    dataset_path = Path(args.dataset)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    output_name = args.output_name or f"{model_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = output_root / output_name
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset, _ = load_dataset(dataset_path)
    model, config = load_model(model_path, device)
    y_true, y_pred, y_score = evaluate_model(model, dataset, device)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
    }

    cm = confusion_matrix(y_true, y_pred)
    write_confusion_csv(output_dir, cm)
    write_predictions_csv(output_dir, y_true, y_pred, y_score)
    plot_confusion_matrix(output_dir, cm)

    if len(np.unique(y_true)) == 2:
        fpr, tpr, thresholds = roc_curve(y_true, y_score)
        roc_auc = float(roc_auc_score(y_true, y_score))
        metrics["roc_auc"] = roc_auc
        write_roc_csv(output_dir, fpr, tpr, thresholds)
        plot_roc(output_dir, fpr, tpr, roc_auc)
        plot_score_histogram(output_dir, y_score, y_true)

    write_summary_csv(output_dir, model_path, dataset_path, config, metrics)

    print(f"Saved evaluation outputs to: {output_dir}")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
