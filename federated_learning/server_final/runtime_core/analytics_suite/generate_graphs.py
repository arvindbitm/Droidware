#!/usr/bin/env python3
import os
from pathlib import Path

import pandas as pd

try:
    import matplotlib.pyplot as plt
except Exception as exc:
    raise SystemExit(f"matplotlib is required to generate graphs: {exc}")


ROOT = Path(__file__).resolve().parent
CLIENT_DIR = ROOT / "client"
GRAPH_DIR = ROOT / "graphs"
GRAPH_DIR.mkdir(exist_ok=True)


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"Skipping {path}: {exc}")
        return None


def save_line_plot(df, x_col, y_cols, title, output_name):
    if df is None or df.empty:
        return
    missing = [col for col in [x_col] + y_cols if col not in df.columns]
    if missing:
        print(f"Skipping {output_name}; missing columns: {missing}")
        return
    plt.figure(figsize=(10, 6))
    for col in y_cols:
        plt.plot(df[x_col], pd.to_numeric(df[col], errors="coerce"), marker="o", label=col)
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel("Score")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    output_path = GRAPH_DIR / output_name
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Saved {output_path}")


def save_bar_plot(df, x_col, y_col, title, output_name):
    if df is None or df.empty:
        return
    if x_col not in df.columns or y_col not in df.columns:
        print(f"Skipping {output_name}; missing {x_col} or {y_col}")
        return
    counts = df.groupby(x_col)[y_col].count()
    plt.figure(figsize=(9, 5))
    counts.plot(kind="bar")
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel("Count")
    plt.tight_layout()
    output_path = GRAPH_DIR / output_name
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Saved {output_path}")


def save_validation_scatter(df):
    if df is None or df.empty:
        return
    required = ["Accuracy", "Cosine Similarity", "Accepted"]
    if any(col not in df.columns for col in required):
        print("Skipping update validation scatter; required columns not found")
        return
    plot_df = df.copy()
    plot_df["Accuracy"] = pd.to_numeric(plot_df["Accuracy"], errors="coerce")
    plot_df["Cosine Similarity"] = pd.to_numeric(plot_df["Cosine Similarity"], errors="coerce")
    colors = plot_df["Accepted"].map({"yes": "tab:green", "no": "tab:red"}).fillna("tab:gray")
    plt.figure(figsize=(9, 6))
    plt.scatter(plot_df["Cosine Similarity"], plot_df["Accuracy"], c=colors, alpha=0.8)
    plt.title("Update Validation: Accuracy vs Cosine Similarity")
    plt.xlabel("Cosine Similarity")
    plt.ylabel("Server Validation Accuracy")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    output_path = GRAPH_DIR / "update_validation_scatter.png"
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Saved {output_path}")


def main():
    client_train = read_csv(CLIENT_DIR / "client_performance_train.csv")
    client_eval = read_csv(CLIENT_DIR / "client_performance.csv")
    server_perf = read_csv(ROOT / "model_performance.csv")
    update_validation = read_csv(ROOT / "update_validation_log.csv")

    save_line_plot(
        client_train,
        "Epoch",
        ["Training Loss"],
        "Client Training Loss",
        "client_training_loss.png",
    )
    save_line_plot(
        client_train,
        "Epoch",
        ["Accuracy", "F1 Score", "MCC"],
        "Client Training Metrics",
        "client_training_metrics.png",
    )
    save_line_plot(
        client_eval.reset_index().rename(columns={"index": "Round"}) if client_eval is not None else None,
        "Round",
        ["Accuracy", "F1 Score", "MCC"],
        "Client Evaluation Metrics",
        "client_evaluation_metrics.png",
    )
    save_line_plot(
        server_perf.reset_index().rename(columns={"index": "Round"}) if server_perf is not None else None,
        "Round",
        ["Accuracy", "F1 Score", "MCC"],
        "Global Model Performance",
        "server_global_performance.png",
    )
    save_validation_scatter(update_validation)
    save_bar_plot(
        update_validation,
        "Reason",
        "Client IP",
        "Update Validation Decisions",
        "update_validation_reasons.png",
    )


if __name__ == "__main__":
    main()
