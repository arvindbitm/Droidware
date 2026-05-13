#!/usr/bin/env python3
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLIENT_DIR = ROOT / "client"
RESULTS_DIR = ROOT / "adversarial_results"
GRAPHS_DIR = ROOT / "graphs"


def count_rows(path):
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    return max(len(rows) - 1, 0)


def report_file(path):
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return exists, size


def main():
    csv_targets = [
        ROOT / "model_performance.csv",
        ROOT / "update_validation_log.csv",
        CLIENT_DIR / "client_performance.csv",
        CLIENT_DIR / "client_performance_train.csv",
        RESULTS_DIR / "adversarial_summary.csv",
        RESULTS_DIR / "update_validation_details.csv",
    ]
    png_targets = [
        GRAPHS_DIR / "client_training_loss.png",
        GRAPHS_DIR / "client_training_metrics.png",
        GRAPHS_DIR / "client_evaluation_metrics.png",
        GRAPHS_DIR / "server_global_performance.png",
        GRAPHS_DIR / "update_validation_scatter.png",
        GRAPHS_DIR / "update_validation_reasons.png",
        RESULTS_DIR / "fedavg_vs_droidware_accuracy.png",
        RESULTS_DIR / "fedavg_vs_droidware_asr.png",
        RESULTS_DIR / "fedavg_vs_droidware_mcc.png",
        RESULTS_DIR / "update_validation_norms.png",
        RESULTS_DIR / "update_validation_cosine.png",
    ]

    print("CSV summary")
    for path in csv_targets:
        exists, size = report_file(path)
        print(f"- {path.name}: exists={exists}, size={size}, data_rows={count_rows(path)}")

    print("\nPNG summary")
    for path in png_targets:
        exists, size = report_file(path)
        print(f"- {path.name}: exists={exists}, size={size}")


if __name__ == "__main__":
    main()
