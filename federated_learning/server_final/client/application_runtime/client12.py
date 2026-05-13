#!/usr/bin/env python3
import asyncio
import csv
import hashlib
import hmac
import json
import logging
import math
import os
import pickle
import socket
import ssl
import time
import zlib
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from torch import nn, optim
from torch.utils.data import DataLoader, Dataset

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

try:
    from pytorch_tabnet.tab_model import TabNetClassifier, TabNetRegressor
except Exception:
    TabNetClassifier = None
    TabNetRegressor = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
USE_TLS = True
TLS_CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
TLS_KEY_FILE = os.path.join(BASE_DIR, "key.pem")

CLIENT_PERFORMANCE = os.path.join(BASE_DIR, "client_performance.csv")
CLIENT_PERFORMANCE_TRAIN = os.path.join(BASE_DIR, "client_performance_train.csv")
TRAINING_METRICS_FILE = os.path.join(BASE_DIR, "training_metrics.json")
TRAINING_LOSS_PLOT = os.path.join(BASE_DIR, "training_loss_plot.png")
UPDATED_MODEL_FILE = os.path.join(BASE_DIR, "updated_model.pth")
FETCHED_MODEL_FILE = os.path.join(BASE_DIR, "fetched_model.pth")

client_model_config = {}
best_optimizer_state_dict = None


def get_primary_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


MY_IP = get_primary_ip()

log_filename = os.path.join(
    BASE_DIR, f"training_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(),
    ],
)


def ensure_csv(path, fieldnames):
    if not os.path.exists(path):
        with open(path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(fieldnames)


ensure_csv(
    CLIENT_PERFORMANCE,
    [
        "Client IP",
        "Accuracy",
        "Precision",
        "Sensitivity",
        "F1 Score",
        "MCC",
        "Markedness",
        "Youden's J",
        "FMI",
        "Time",
    ],
)
ensure_csv(
    CLIENT_PERFORMANCE_TRAIN,
    [
        "Client IP",
        "Epoch",
        "Training Loss",
        "Accuracy",
        "Precision",
        "Sensitivity",
        "F1 Score",
        "MCC",
        "Markedness",
        "Youden's J",
        "FMI",
        "Time",
    ],
)


async def read_response_ignoring_keep_alive(reader, read_size=4096):
    while True:
        response = await reader.read(read_size)
        response_str = response.decode("utf-8", errors="replace")
        stripped = response_str.strip()
        if stripped and all(line == "KEEP_ALIVE" for line in stripped.splitlines()):
            logging.info("Ignoring KEEP_ALIVE, waiting for server response...")
            continue
        return response_str


async def readline_ignoring_keep_alive(reader):
    while True:
        line = await reader.readline()
        if line.decode("utf-8", errors="replace").strip() == "KEEP_ALIVE":
            logging.info("Ignoring KEEP_ALIVE, waiting for server header...")
            continue
        return line


def ssl_context():
    if not USE_TLS:
        return None
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.load_verify_locations(cafile=TLS_CERT_FILE)
    return context


def compute_all_metrics(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    mcc = matthews_corrcoef(y_true, y_pred)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    cm = confusion_matrix(y_true, y_pred)
    num_classes = len(np.unique(y_true))
    if num_classes == 2 and cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        npv = tn / (tn + fn) if (tn + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        markedness = prec + npv - 1
        youdens_j = rec + specificity - 1
    else:
        markedness = np.nan
        youdens_j = np.nan
    fmi = math.sqrt(prec * rec) if prec >= 0 and rec >= 0 else 0

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "mcc": mcc,
        "markedness": markedness,
        "youdens_j": youdens_j,
        "fmi": fmi,
    }


class CustomDataset(Dataset):
    def __init__(self, data_path):
        try:
            logging.info(f"Loading dataset from {data_path}")
            df = pd.read_csv(data_path, usecols=lambda col: col not in ["Sha256"])
            df.dropna(inplace=True)
            label_col = df.columns[-1]
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if label_col not in numeric_cols:
                features = df.select_dtypes(include=["number"]).copy()
                label_encoder = LabelEncoder()
                df[label_col] = label_encoder.fit_transform(df[label_col])
            else:
                features = df.drop(columns=[label_col]).copy()
            x_np = features.values.astype(np.float32)
            scaler = StandardScaler()
            x_np = scaler.fit_transform(x_np)
            x_np = np.expand_dims(x_np, axis=1)
            self.features = torch.tensor(x_np, dtype=torch.float32)
            self.labels = torch.tensor(df[label_col].values, dtype=torch.long)
            logging.info(f"Dataset loaded successfully, size: {len(self.features)}")
        except Exception as exc:
            logging.error(f"Error loading dataset: {exc}")
            raise

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


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
            x_pooled = x.mean(dim=1)
        elif self.pooling == "max":
            x_pooled = x.max(dim=1)[0]
        elif self.pooling == "concat":
            x_avg = x.mean(dim=1)
            x_max = x.max(dim=1)[0]
            x_pooled = torch.cat([x_avg, x_max], dim=1)
        else:
            raise ValueError("Unsupported pooling type.")
        return self.network(x_pooled)


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
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers
        )
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
    ):
        super().__init__()
        self.feedforward = DeepFeedforwardNN(
            input_dim, ff_hidden_dims, embed_dim, pooling, dropout
        )
        self.ft_transformer = FTTransformer(
            input_dim, embed_dim, num_heads, num_layers, dropout
        )
        self.combined_fc = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, final_output_dim),
        )

    def forward(self, x):
        out_ff = self.feedforward(x)
        out_ft = self.ft_transformer(x)
        combined = torch.cat([out_ff, out_ft], dim=1)
        return self.combined_fc(combined)


def create_model_from_state_dict(state_dict, input_size=None):
    layer_names = list(state_dict.keys())
    state_input_size = state_dict[layer_names[0]].shape[1]
    output_size = state_dict[layer_names[-1]].shape[0]
    input_size = input_size or state_input_size
    model = nn.Sequential(
        nn.Linear(input_size, 128),
        nn.ReLU(),
        nn.Linear(128, output_size),
    )
    logging.info(f"Model created with input size {input_size} and output size {output_size}")
    return model


def create_hybrid_model(config):
    logging.info("Creating HybridModel using configuration from checkpoint")
    return HybridModel(
        input_dim=config["input_dim"],
        ff_hidden_dims=config["ff_hidden_dims"],
        embed_dim=config["embed_dim"],
        final_output_dim=config["final_output_dim"],
        pooling=config.get("pooling", "avg"),
        dropout=config.get("dropout", 0.2),
        num_heads=config.get("num_heads", 4),
        num_layers=config.get("num_layers", 2),
    )


def move_optimizer_state_to_device(optimizer, device):
    for state in optimizer.state.values():
        for key, value in list(state.items()):
            if torch.is_tensor(value):
                state[key] = value.to(device)


async def authenticate(server_address, username, password):
    host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
    reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_context())

    writer.write(f"AUTH_USERNAME|{username}|{password}\n".encode())
    await writer.drain()
    response_str = await read_response_ignoring_keep_alive(reader)
    if "OTP_SENT" not in response_str:
        logging.error(f"Authentication failed: {response_str}")
        writer.close()
        await writer.wait_closed()
        return None, None, None

    email = response_str.split("|")[1].strip()
    otp = input(f"Enter OTP sent to {email}: ").strip()

    writer.write(f"VERIFY_OTP|{username}|{otp}\n".encode())
    await writer.drain()
    response_str = await read_response_ignoring_keep_alive(reader)
    if "TOKEN_ISSUED" not in response_str:
        logging.error(f"OTP verification failed: {response_str}")
        writer.close()
        await writer.wait_closed()
        return None, None, None

    parts = response_str.strip().split("|")
    token, refresh_token, hmac_key = parts[1], parts[2], parts[3]
    logging.info("Authentication successful")
    writer.close()
    await writer.wait_closed()
    return token, refresh_token, hmac_key


async def fetch_model(server_address, token, hmac_key):
    host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
    reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_context())

    request_data = "GET_MODEL"
    signature = hmac.new(hmac_key.encode(), request_data.encode(), hashlib.sha256).hexdigest()
    writer.write(f"{token}|{request_data}|{signature}\n".encode())
    await writer.drain()

    header_line = await readline_ignoring_keep_alive(reader)
    header = header_line.decode("utf-8", errors="replace").strip()
    header_parts = dict(part.split(":", 1) for part in header.split("|") if ":" in part)
    file_ext = header_parts.get("TYPE")
    payload_size = int(header_parts["SIZE"]) if "SIZE" in header_parts else None
    if not file_ext or payload_size is None:
        raise ValueError(f"Missing or invalid model header from server: {header}")

    compressed_model = await reader.readexactly(payload_size)
    writer.close()
    await writer.wait_closed()

    model_data = zlib.decompress(compressed_model)
    model_file_path = os.path.join(BASE_DIR, f"fetched_model{file_ext}")
    with open(model_file_path, "wb") as f:
        f.write(model_data)
    logging.info(f"Model fetched successfully: {model_file_path}")
    return model_file_path, file_ext


def initialize_model(model_path):
    global best_optimizer_state_dict, client_model_config

    extension = os.path.splitext(model_path)[1]
    if extension in [".pth", ".pt"]:
        checkpoint = torch.load(
            model_path,
            map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
        )
        if isinstance(checkpoint, dict):
            if "model_state_dict" in checkpoint and "config" in checkpoint:
                client_model_config = checkpoint["config"]
                logging.info(f"Loaded model configuration: {client_model_config}")
                if client_model_config.get("model_type") == "HybridModel":
                    model = create_hybrid_model(client_model_config)
                else:
                    model = create_model_from_state_dict(checkpoint["model_state_dict"])
                model.load_state_dict(checkpoint["model_state_dict"], strict=False)
                if "optimizer_state_dict" in checkpoint:
                    best_optimizer_state_dict = checkpoint["optimizer_state_dict"]
                    if isinstance(best_optimizer_state_dict, tuple):
                        best_optimizer_state_dict = best_optimizer_state_dict[0]
            elif "model_state_dict" in checkpoint:
                model = create_model_from_state_dict(checkpoint["model_state_dict"])
                model.load_state_dict(checkpoint["model_state_dict"], strict=False)
            else:
                model = create_model_from_state_dict(checkpoint)
                model.load_state_dict(checkpoint, strict=False)
        else:
            model = checkpoint
    elif extension == ".pkl":
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
        except Exception:
            model = joblib.load(model_path)
    else:
        raise ValueError(f"Unsupported model format: {extension}")
    return model


def append_metrics_row(path, metrics, extra_columns=None):
    row = [MY_IP]
    if extra_columns:
        row.extend(extra_columns)
    row.extend(
        [
            f"{metrics['accuracy']:.4f}",
            f"{metrics['precision']:.4f}",
            f"{metrics['recall']:.4f}",
            f"{metrics['f1_score']:.4f}",
            f"{metrics['mcc']:.4f}",
            f"{metrics['markedness']:.4f}",
            f"{metrics['youdens_j']:.4f}",
            f"{metrics['fmi']:.4f}",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ]
    )
    with open(path, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)


def train_local_model(model, dataset_path, epochs=10, batch_size=32, learning_rate=0.00001):
    global best_optimizer_state_dict

    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found at: {dataset_path}")

    dataset = CustomDataset(dataset_path)

    if TabNetClassifier is not None and isinstance(model, TabNetClassifier):
        x_train, y_train = dataset.features.numpy(), dataset.labels.numpy()
        x_train_split, x_valid_split, y_train_split, y_valid_split = train_test_split(
            x_train, y_train, test_size=0.2, random_state=42
        )
        model.fit(
            X_train=x_train_split,
            y_train=y_train_split,
            eval_set=[(x_valid_split, y_valid_split)],
            eval_name=["validation"],
            eval_metric=["accuracy"],
            max_epochs=epochs,
            batch_size=batch_size,
            patience=10,
            virtual_batch_size=128,
            num_workers=0,
            drop_last=False,
        )
        return model

    if not isinstance(model, nn.Module):
        raise ValueError(f"Unsupported model type: {type(model)}")

    train_idx, valid_idx = train_test_split(
        range(len(dataset)),
        test_size=0.2,
        random_state=42,
        stratify=dataset.labels.numpy() if len(np.unique(dataset.labels.numpy())) > 1 else None,
    )
    train_dataset = torch.utils.data.Subset(dataset, train_idx)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        pin_memory=torch.cuda.is_available(),
    )

    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    if best_optimizer_state_dict:
        try:
            optimizer.load_state_dict(best_optimizer_state_dict)
            move_optimizer_state_to_device(optimizer, device=torch.device("cpu"))
            logging.info("Optimizer state loaded successfully.")
        except ValueError as exc:
            logging.warning(f"Optimizer state mismatch: {exc}. Resetting optimizer.")

    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    move_optimizer_state_to_device(optimizer, device)

    epoch_metrics = []
    losses = []
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        all_preds = []
        all_labels = []

        for features, labels in train_loader:
            features, labels = features.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item()

            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

        avg_loss = total_loss / max(len(train_loader), 1)
        metrics = compute_all_metrics(np.array(all_labels), np.array(all_preds))
        append_metrics_row(
            CLIENT_PERFORMANCE_TRAIN,
            metrics,
            extra_columns=[f"{epoch + 1}", f"{avg_loss:.6f}"],
        )
        epoch_metrics.append({"epoch": epoch + 1, "loss": avg_loss, **metrics})
        losses.append(avg_loss)
        logging.info(
            f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}, "
            f"Accuracy: {metrics['accuracy']:.4f}"
        )
        scheduler.step()

    with open(TRAINING_METRICS_FILE, "w") as f:
        json.dump(epoch_metrics, f, indent=2)

    if plt is not None and losses:
        plt.plot(range(1, len(losses) + 1), losses, marker="o")
        plt.title("Training Loss Over Epochs")
        plt.xlabel("Epochs")
        plt.ylabel("Loss")
        plt.savefig(TRAINING_LOSS_PLOT)
        plt.close()

    best_optimizer_state_dict = optimizer.state_dict()
    logging.info("Local model training completed")
    return model


def evaluate_model(model, dataset_path):
    dataset = CustomDataset(dataset_path)
    y_true = []
    y_pred = []

    if isinstance(model, nn.Module):
        test_loader = DataLoader(
            dataset,
            batch_size=16,
            shuffle=False,
            num_workers=0,
            pin_memory=torch.cuda.is_available(),
        )
        model.eval()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, predicted = torch.max(outputs, 1)
                y_true.extend(labels.cpu().numpy())
                y_pred.extend(predicted.cpu().numpy())
    elif hasattr(model, "predict"):
        y_pred = model.predict(dataset.features.numpy())
        y_true = dataset.labels.numpy()
    else:
        raise ValueError(f"Unsupported model type: {type(model)}")

    metrics = compute_all_metrics(np.array(y_true), np.array(y_pred))
    append_metrics_row(CLIENT_PERFORMANCE, metrics)
    logging.info(f"Evaluation metrics computed: {metrics}")
    return {
        "accuracy": metrics["accuracy"],
        "f1_score": metrics["f1_score"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
    }


def save_model_checkpoint(model, file_path):
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": best_optimizer_state_dict,
        "config": client_model_config,
    }
    torch.save(checkpoint, file_path)
    logging.info(f"Model checkpoint saved: {file_path}")


async def send_update(server_address, token, hmac_key, model, max_retries=3):
    host, port = server_address.split(":") if ":" in server_address else (server_address, "6000")
    model.to("cpu")
    save_model_checkpoint(model, UPDATED_MODEL_FILE)
    with open(UPDATED_MODEL_FILE, "rb") as f:
        compressed_data = zlib.compress(f.read())

    for attempt in range(1, max_retries + 1):
        try:
            reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_context())
            request_data = "SEND_UPDATE"
            signature = hmac.new(
                hmac_key.encode(), request_data.encode(), hashlib.sha256
            ).hexdigest()
            writer.write(f"{token}|{request_data}|{signature}\n".encode())
            await writer.drain()

            ready = await readline_ignoring_keep_alive(reader)
            if ready.decode("utf-8", errors="replace").strip() != "READY_FOR_UPDATE":
                raise RuntimeError(
                    f"Server did not accept update upload: {ready.decode('utf-8', errors='replace').strip()}"
                )

            writer.write(f"TYPE:.pth|SIZE:{len(compressed_data)}\n".encode())
            await writer.drain()
            writer.write(compressed_data)
            await writer.drain()

            response_str = await read_response_ignoring_keep_alive(reader)
            writer.close()
            await writer.wait_closed()
            if "UPDATE_RECEIVED" in response_str:
                logging.info("Model update sent successfully")
                return
            logging.error(
                f"Attempt {attempt} - update rejected. Server response: {response_str}"
            )
        except Exception as exc:
            logging.error(f"Attempt {attempt} - error sending model to server: {exc}")
        if attempt < max_retries:
            logging.info("Retrying in 5 seconds...")
            time.sleep(5)

    raise RuntimeError("Max retries reached. Update not sent.")


def resolve_dataset_path(env_var, preferred_names):
    candidates = [os.environ.get(env_var)]
    candidates.extend(preferred_names)
    candidates.extend(os.path.join(PROJECT_DIR, name) for name in preferred_names)
    candidates.append(os.path.join(PROJECT_DIR, "Droidware2025_Set2.csv"))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        f"No dataset found. Set {env_var} or place a Droidware CSV under {PROJECT_DIR}."
    )


def main(server_address, token=None, hmac_key=None):
    train_dataset_path = resolve_dataset_path(
        "DROIDWARE_TRAIN_DATA",
        ["Droidware2025_final_Set8.csv", "Droidware2025_Set4.csv"],
    )
    test_dataset_path = resolve_dataset_path(
        "DROIDWARE_TEST_DATA",
        ["Droidware2025_final_Set1.csv", "Droidware2025_Set2.csv"],
    )

    model_file_path, _ = asyncio.run(fetch_model(server_address, token, hmac_key))
    model = initialize_model(model_file_path)
    model = train_local_model(model, train_dataset_path)
    evaluation_metrics = evaluate_model(model, test_dataset_path)
    print("Evaluation Metrics:", evaluation_metrics)
    asyncio.run(send_update(server_address, token, hmac_key, model))


if __name__ == "__main__":
    server_address = (
        input("Enter the server address (default 127.0.0.1:6000): ").strip()
        or "127.0.0.1:6000"
    )
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    token, refresh_token, hmac_key = asyncio.run(
        authenticate(server_address, username, password)
    )
    if token and hmac_key:
        rounds = int(os.environ.get("DROIDWARE_CLIENT_ROUNDS", "1"))
        for _ in range(rounds):
            main(server_address, token=token, hmac_key=hmac_key)
