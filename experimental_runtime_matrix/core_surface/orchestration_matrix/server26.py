import os
# Suppress TensorFlow info/warnings (only fatal errors will be printed)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import zlib
import pickle
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    matthews_corrcoef, confusion_matrix
)
import pandas as pd
# from tensorflow.keras.models import load_model as tf_load_model
import socket
from functools import partial
import joblib
import json
import numpy as np
import csv  # For CSV logging
import io   # For BytesIO in torch.save
import tempfile
import math
import ssl  # For TLS support
import warnings
import hashlib  # For computing SHA-256 hashes
import copy
import torch.optim as optim
from sklearn.preprocessing import StandardScaler, LabelEncoder
# Import logging manager
from logging_manager import get_logger, get_master_logger, RequestContext, master_error, master_info
import aiofiles  # Added for asynchronous file I/O
from mfa import generate_otp, send_otp_email, send_otp_sms, verify_otp, generate_totp_secret, verify_totp
from tls_certificate.tls_certificate import ensure_tls_certificates


warnings.filterwarnings("ignore")

# -------------------------
# Global Configuration & Directories
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
USE_TLS = True
TLS_CERT_FILE = os.path.join(PROJECT_ROOT, "cert.pem")
TLS_KEY_FILE = os.path.join(PROJECT_ROOT, "key.pem")

model_lock = asyncio.Lock()

model_path = os.path.join(PROJECT_ROOT, "best_hybrid_model_state.pth")
model_versions_path = os.path.join(PROJECT_ROOT, "model_versions")
log_file = os.path.join(PROJECT_ROOT, "server_logs.log")
test_dataset_path = os.path.join(PROJECT_ROOT, "Droidware2025_Set2.csv")
model_performance_log = os.path.join(PROJECT_ROOT, "model_performance.csv")
update_validation_log = os.path.join(PROJECT_ROOT, "update_validation_log.csv")
client_log_csv = os.path.join(PROJECT_ROOT, "client_log.csv")
config_hash_path = os.path.join(PROJECT_ROOT, "best_hybrid_model_config_hash.json")
blacklist_file = os.path.join(PROJECT_ROOT, "blacklist.json")
master_log_file = os.path.join(PROJECT_ROOT, "master_log.log")

os.makedirs(client_models_dir := os.path.join(PROJECT_ROOT, "client_models"), exist_ok=True)
os.makedirs(model_versions_path, exist_ok=True)

global_model_folder = os.path.join(PROJECT_ROOT, "global_model")
os.makedirs(global_model_folder, exist_ok=True)
global_model_file = os.path.join(global_model_folder, "global_model_latest.pth")
COSINE_ANOMALY_LAMBDA = 2.0
ROLLBACK_ACCURACY_DROP = 0.03


# Initialize files if they don’t exist
for file, initial_content in [
    (master_log_file,{}),
    (blacklist_file, {}),
    (model_performance_log, ["Client IP", "Accuracy", "Precision", "Sensitivity", "F1 Score", "MCC", "Markedness", "Youden's J", "FMI", "Time"]),
    (update_validation_log, ["Time", "Client IP", "Accuracy", "Precision", "Sensitivity", "F1 Score", "MCC", "Markedness", "Youden's J", "FMI", "Cosine Similarity", "Accepted", "Reason"]),
    (client_log_csv, ["timestamp", "client_ip", "action", "details"])
]:
    if not os.path.exists(file):
        if file.endswith(".json"):
            with open(file, 'w') as f:
                json.dump(initial_content, f)
        elif file.endswith(".csv"):
            with open(file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(initial_content)
        
        elif file.endswith(".log"):  # Add this
            with open(file, 'w') as f:
                f.write("")  # Create empty log file


# -------------------------
# Logging Configuration (Updated)
# -------------------------
# Initialize loggers
server_logger = get_logger("FederatedServer", "server_logs.log")
master_logger = get_master_logger()
# logger = logging.getLogger("FederatedServer")
# logger.setLevel(logging.DEBUG)

# # File handler for logging to file
# handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
# formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)

# # Console handler for printing logs to terminal
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)

# #Master logger from server26.py
# master_logger = logging.getLogger("MasterLog")
# master_logger.setLevel(logging.DEBUG)
# master_handler = RotatingFileHandler("master_log.log", maxBytes=5*1024*1024, backupCount=5)
# master_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(file_name)s - %(message)s')
# master_handler.setFormatter(master_formatter)
# master_logger.addHandler(master_handler)
# master_logger.addHandler(logging.StreamHandler())
# logger.addHandler(master_handler)  # Link server logger to master log
from firewall import rate_limit, check_geo_location
from auth import AuthManager
from cookies import create_cookie, verify_cookie, invalidate_cookie

SESSION_TIMEOUT = 300  # CHANGED: Session expiration time (5 minutes)
session_tracker = {}  # CHANGED: Track active sessions and their last activity
client_sessions = {}  # CHANGED: Store session cookies for clients


def log_client_event(client_ip, action, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(client_log_csv, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, client_ip, action, details])
    server_logger.info(f"Client event logged: IP={client_ip}, Action={action}, Details={details}")
    master_logger.info(f"Client event: IP={client_ip}, Action={action}, Details={details}")

def _metric_value(metrics, key):
    if not metrics:
        return np.nan
    value = metrics.get(key, np.nan)
    try:
        return float(value)
    except Exception:
        return np.nan

def log_update_validation_records(records, accepted_indices):
    accepted_set = set(accepted_indices)
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(update_validation_log, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        for idx, record in enumerate(records):
            metrics = record.get("metrics")
            cosine = record.get("cosine_similarity")
            accepted = idx in accepted_set
            reason = "accepted" if accepted else record.get("reason", "rejected")
            row = [
                log_time,
                record.get("client_ip", ""),
                f"{_metric_value(metrics, 'accuracy'):.4f}",
                f"{_metric_value(metrics, 'precision'):.4f}",
                f"{_metric_value(metrics, 'recall'):.4f}",
                f"{_metric_value(metrics, 'f1_score'):.4f}",
                f"{_metric_value(metrics, 'mcc'):.4f}",
                f"{_metric_value(metrics, 'markedness'):.4f}",
                f"{_metric_value(metrics, 'youdens_j'):.4f}",
                f"{_metric_value(metrics, 'fmi'):.4f}",
                f"{float(cosine):.6f}" if cosine is not None and math.isfinite(cosine) else "nan",
                "yes" if accepted else "no",
                reason,
            ]
            writer.writerow(row)

# -------------------------
# Custom Dataset Definition
# -------------------------
class CustomDataset(Dataset):
    def __init__(self, data_path):
        try:
            df = pd.read_csv(data_path, usecols=lambda col: col not in ['Sha256'])
            df.dropna(inplace=True)
            LABEL = df.columns[-1]
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if LABEL not in numeric_cols:
                features = df.select_dtypes(include=['number']).copy()
                le = LabelEncoder()
                df[LABEL] = le.fit_transform(df[LABEL])
            else:
                features = df.drop(columns=[LABEL]).copy()
            X_np = features.values.astype(np.float32)
            scaler = StandardScaler()
            X_np = scaler.fit_transform(X_np)
            X_np = np.expand_dims(X_np, axis=1)  # (n_samples, 1, n_features)
            self.features = torch.tensor(X_np, dtype=torch.float32)
            self.labels = torch.tensor(df[LABEL].values, dtype=torch.long)
            server_logger.info(f"Dataset loaded from {data_path}, size: {len(self.features)}")
        except Exception as e:
            raise ValueError(f"Error loading dataset: {e}")

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

# -------------------------
# Metric Computation Functions
# -------------------------
def compute_metrics(y_true, y_pred):
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "mcc": matthews_corrcoef(y_true, y_pred)
    }

def compute_all_metrics(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average='macro', zero_division=0)
    rec = recall_score(y_true, y_pred, average='macro', zero_division=0)
    f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
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
        "fmi": fmi
    }

# -------------------------
# Helper Functions for Model Creation & Parameter Handling
# -------------------------
def create_model_from_state_dict(state_dict, input_size=None):
    try:
        server_logger.info("Creating model from state_dict")
        layer_names = list(state_dict.keys())
        state_input_size = state_dict[layer_names[0]].shape[1]
        output_size = state_dict[layer_names[-1]].shape[0]
        input_size = input_size or state_input_size
        model = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Linear(128, output_size)
        )
        server_logger.info(f"Model created with input size {input_size} and output size {output_size}")
        return model
    except Exception as e:
        server_logger.error(f"Error creating model: {e}")
        raise

def get_model_parameters(model):
    if hasattr(model, "state_dict"):
        return {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
    elif hasattr(model, "get_weights"):
        return model.get_weights()
    elif model.__class__.__name__ == "TabNetClassifier":
        return {k: v.detach().cpu().numpy() for k, v in model.__dict__.items() if isinstance(v, torch.Tensor)}
    else:
        raise ValueError("Unsupported model type for parameter extraction.")

def set_model_parameters(model, params):
    if hasattr(model, "state_dict"):
        state = model.state_dict()
        new_state = {}
        for k, v in state.items():
            if k in params:
                new_state[k] = torch.tensor(params[k])
            else:
                new_state[k] = v
        model.load_state_dict(new_state, strict=False)
    elif hasattr(model, "set_weights"):
        model.set_weights(params)
    elif model.__class__.__name__ == "TabNetClassifier":
        for k, v in params.items():
            setattr(model, k, torch.tensor(v))
    else:
        raise ValueError("Unsupported model type for setting parameters.")

def flatten_state_dict(state_dict):
    """Return a single float vector for cosine-based update validation."""
    vectors = []
    for tensor in state_dict.values():
        if torch.is_tensor(tensor):
            vectors.append(tensor.detach().float().cpu().reshape(-1))
    if not vectors:
        return torch.empty(0)
    return torch.cat(vectors)

def cosine_similarity_from_states(base_state, candidate_state):
    base_vec = flatten_state_dict(base_state)
    candidate_vec = flatten_state_dict(candidate_state)
    if base_vec.numel() == 0 or candidate_vec.numel() == 0 or base_vec.numel() != candidate_vec.numel():
        return None
    base_norm = torch.norm(base_vec)
    candidate_norm = torch.norm(candidate_vec)
    if base_norm.item() == 0 or candidate_norm.item() == 0:
        return None
    return torch.dot(base_vec, candidate_vec).item() / (base_norm.item() * candidate_norm.item())

def update_global_model(global_model, client_models):
    n = len(client_models)
    try:
        for client_model in client_models:
            for global_param, update_param in zip(global_model.parameters(), client_model.parameters()):
                global_param.data += update_param.data / n
    except Exception as e:
        global_weights = get_model_parameters(global_model)
        client_weights_list = [get_model_parameters(cm) for cm in client_models]
        if isinstance(global_weights, dict):
            aggregated = {}
            for key in global_weights:
                updates = [client_weights[key] for client_weights in client_weights_list]
                aggregated[key] = global_weights[key] + np.mean(updates, axis=0)
            set_model_parameters(global_model, aggregated)
        elif isinstance(global_weights, list):
            aggregated = []
            for i in range(len(global_weights)):
                updates = [client_weights[i] for client_weights in client_weights_list]
                aggregated.append(global_weights[i] + np.mean(updates, axis=0))
            set_model_parameters(global_model, aggregated)
        else:
            raise ValueError("Unsupported parameters format during aggregation.")

# -------------------------
# HybridModel Definition and Helper Function
# -------------------------
class DeepFeedforwardNN(nn.Module):
    def __init__(self, input_dim, hidden_dims, embed_dim, pooling='avg', dropout=0.2):
        super(DeepFeedforwardNN, self).__init__()
        self.pooling = pooling
        if pooling == 'concat':
            effective_input_dim = input_dim * 2
        else:
            effective_input_dim = input_dim
        layers = []
        prev_dim = effective_input_dim
        for h_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, h_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = h_dim
        layers.append(nn.Linear(prev_dim, embed_dim))
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        if self.pooling == 'avg':
            x_pooled = x.mean(dim=1)
        elif self.pooling == 'max':
            x_pooled = x.max(dim=1)[0]
        elif self.pooling == 'concat':
            x_avg = x.mean(dim=1)
            x_max = x.max(dim=1)[0]
            x_pooled = torch.cat([x_avg, x_max], dim=1)
        else:
            raise ValueError("Unsupported pooling type.")
        return self.network(x_pooled)

class FTTransformer(nn.Module):
    def __init__(self, input_dim, embed_dim, num_heads=4, num_layers=2, dropout=0.2):
        super(FTTransformer, self).__init__()
        self.embedding = nn.Linear(input_dim, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim, nhead=num_heads, dropout=dropout, batch_first=True)
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
    def __init__(self, input_dim, ff_hidden_dims, embed_dim, final_output_dim,
                 pooling='avg', dropout=0.2, num_heads=4, num_layers=2):
        super(HybridModel, self).__init__()
        self.feedforward = DeepFeedforwardNN(input_dim, ff_hidden_dims, embed_dim, pooling, dropout)
        self.ft_transformer = FTTransformer(input_dim, embed_dim, num_heads, num_layers, dropout)
        self.combined_fc = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, final_output_dim)
        )
    
    def forward(self, x):
        out_ff = self.feedforward(x)
        out_ft = self.ft_transformer(x)
        combined = torch.cat([out_ff, out_ft], dim=1)
        return self.combined_fc(combined)

def create_hybrid_model(config):
    server_logger.info("Creating HybridModel using configuration from checkpoint.")
    return HybridModel(
        input_dim=config["input_dim"],
        ff_hidden_dims=config["ff_hidden_dims"],
        embed_dim=config["embed_dim"],
        final_output_dim=config["final_output_dim"],
        pooling=config["pooling"],
        dropout=config["dropout"],
        num_heads=config["num_heads"],
        num_layers=config["num_layers"]
    )

# -------------------------
# Integrity Check Helper Function
# -------------------------
def verify_config_integrity(config):
    try:
        server_logger.info("Verifying config integrity")
        config_json = json.dumps(config, sort_keys=True)
        computed_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()
        with open(config_hash_path, "r") as f:
            data = json.load(f)
        stored_hash = data.get("sha256")
        if stored_hash is None:
            server_logger.error("Integrity Check: No 'sha256' key found in config hash file.")
            master_error("Integrity Check: No 'sha256' key found in config hash file.")
            return False
        if computed_hash == stored_hash:
            server_logger.info("Integrity Check Passed")
            master_info("Integrity Check Passed")

            return True
        else:
            server_logger.error(f"Integrity Check Failed: Computed {computed_hash} != Stored {stored_hash}")
            master_error(f"Integrity Check Failed: Computed {computed_hash} != Stored {stored_hash}")
            return False
    except Exception as e:
        server_logger.error(f"Integrity Check Exception: {e}")
        master_error(f"Integrity Check Exception: {e}")
        return False


#Gete thing from jason
def get_server_address():
    host = os.getenv("DROIDWARE_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("DROIDWARE_SERVER_PORT", "6000"))
    return host, port
    
# host , port = get_config_from_json("ip_url.json")
# -------------------------
# FederatedLearningServer Class Definition
# -------------------------
class FederatedLearningServer:
    def __init__(self):
        server_logger = get_logger("FederatedServer", "server_logs.log")
        self.master_logger = get_master_logger()
        self.host , self.port = get_server_address()
        server_logger.debug(f"host: {self.host}, port: {self.port}")
        # self.host = host
        # self.port = port
        self.lr = 0.00001
        self.epochs = 5
        self.pre_update_state = None  # Stores model parameters
        self.pre_update_config = None  # Stores model configuration
        self.pre_update_optimizer_state = None  # Stores optimizer state

        self.model_version = 0
        self.model, self.optimizer_state = self.initialize_model()
        if(self.optimizer_state is None):
            server_logger.info(f"optimizer_state: {self.optimizer_state}")
        if not hasattr(self, "model_config") or not self.model_config:
            server_logger.warning("WARNING: Model config was empty after initialization! Using default config.")
            self.model_config = {"model_type": "HybridModel"}
        server_logger.info(f"Final model config after init: {self.model_config}")

        self.update_queue = []
        self.previous_accuracy = None

        self.connection_attempts = {}  # {client_ip: (count, last_timestamp)}

        self.blacklist = {} # Load blacklist at initialization
        self.blacklist_file = blacklist_file
        self.blacklist_lock = asyncio.Lock()  # Lock for async file operations
        self.blacklist_changed = False  # Flag to track changes for batch saving
        self.blacklist_expiry_hours = 24 # Blacklist entries expire after 24 hours
        self.base_blacklist_threshold = 5  # Base threshold for blacklisting
        self.permanent_reasons = {"manual override"}  # Reasons that result in permanent bans
        self.auth_manager = AuthManager()
        bootstrap_admin_email = os.getenv("DROIDWARE_ADMIN_EMAIL", "admin@droidware.local")
        bootstrap_admin_password = os.getenv("DROIDWARE_ADMIN_PASSWORD", "change-me-admin-password")
        success, totp_secret = self.auth_manager.register_user("admin", bootstrap_admin_password, bootstrap_admin_email, is_admin=True)
        if success and totp_secret:
            server_logger.info(f"Admin registered. TOTP secret: {totp_secret} (Save this for authenticator app)")



    # Added method to load blacklist from file
    async def load_blacklist(self):
        """Load the blacklist from a file asynchronously and convert timestamps."""
        server_logger.info(f"Loading blacklist from {self.blacklist_file}")
        try:
            if os.path.exists(self.blacklist_file):
                async with aiofiles.open(self.blacklist_file, 'r') as f:
                    content = await f.read()
                    blacklist_data = json.loads(content)
                    if isinstance(blacklist_data, dict):
                        # Convert timestamp strings back to datetime objects
                        self.blacklist = {
                            ip: {
                                "timestamp": datetime.strptime(info["timestamp"], "%Y-%m-%d %H:%M:%S"),
                                "attempts": info["attempts"],
                                "reason": info["reason"]
                            }
                            for ip, info in blacklist_data.items()
                        }
                        server_logger.info(f"Loaded blacklist with {len(self.blacklist)} IPs from {self.blacklist_file}")
                        return self.blacklist
                    
                    
                    server_logger.warning("Blacklist file contains invalid data; initializing empty blacklist.")
                    return {}
            server_logger.info(f"No blacklist file found at {self.blacklist_file}; initializing empty blacklist.")
            return {}
        except Exception as e:
            server_logger.error(f"Failed to load blacklist from {self.blacklist_file}: {e}. Using empty blacklist.")
            return {}
    
    
    async def save_blacklist(self):
        """Save the blacklist to a file asynchronously with all metadata."""
        if not self.blacklist_changed:
            return
        async with self.blacklist_lock:
            try:
                # Serialize datetime to string for JSON
                serialized_blacklist = {
                    ip: {
                        "timestamp": info["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        "attempts": info["attempts"],
                        "reason": info["reason"]
                    }
                    for ip, info in self.blacklist.items()
                }
                async with aiofiles.open(self.blacklist_file, 'w') as f:
                    await f.write(json.dumps(serialized_blacklist, indent=2))
                self.blacklist_changed = False
                server_logger.debug(f"Blacklist saved to {self.blacklist_file} with {len(self.blacklist)} IPs.")
            except Exception as e:
                server_logger.error(f"Failed to save blacklist to {self.blacklist_file}: {e}")

    async def clean_expired_blacklist_entries(self):
        """Remove expired blacklist entries based on timestamp."""
        current_time = datetime.now()
        expired = []
        history_file = "blacklist_history.json"
        history = await self.load_blacklist_history(history_file)  # CHANGED: Load history for updates

        async with self.blacklist_lock:
            for ip, info in self.blacklist.items():
                if info["reason"] in self.permanent_reasons:
                    continue 
                time_diff_hours = (current_time - info["timestamp"]).total_seconds() / 3600
                if time_diff_hours > self.blacklist_expiry_hours:
                    expired.append(ip)
                    # CHANGED: Save only necessary data (attempts and timestamp) to history
                    history[ip] = {"attempts": info["attempts"], "timestamp": info["timestamp"]}

            for ip in expired:
                server_logger.info(f"Removing expired blacklist entry for {ip}: Added at {self.blacklist[ip]['timestamp']}")
                del self.blacklist[ip]
                self.blacklist_changed = True
        if expired:
            await self.save_blacklist()
            server_logger.debug(f"Cleaned {len(expired)} expired blacklist entries.")

    #New method to load minimal history data
    async def load_blacklist_history(self, history_file):
        """Load minimal blacklist history."""
        try:
            if os.path.exists(history_file):
                async with aiofiles.open(history_file, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                    if isinstance(data, dict):
                        return {
                            ip: {
                                "attempts": info["attempts"],
                                "timestamp": datetime.strptime(info["timestamp"], "%Y-%m-%d %H:%M:%S")
                            }
                            for ip, info in data.items()
                        }
            return {}
        except Exception as e:
            server_logger.error(f"Failed to load blacklist history: {e}")
            return {}

    # CHANGED: New method to save minimal history data
    async def save_blacklist_history(self, history, history_file):
        """Save minimal blacklist history."""
        try:
            serialized_history = {
                ip: {
                    "attempts": info["attempts"],
                    "timestamp": info["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                }
                for ip, info in history.items()
            }
            async with aiofiles.open(history_file, 'w') as f:
                await f.write(json.dumps(serialized_history, indent=2))
        except Exception as e:
            server_logger.error(f"Failed to save blacklist history: {e}")
            master_error(f"Failed to save blacklist history: {e}")

    def clean_connection_attempts(self):
        """NEW: Periodically clean old connection attempts to manage memory."""
        current_time = datetime.now()
        self.connection_attempts = {
            ip: (count, ts) for ip, (count, ts) in self.connection_attempts.items()
            if (current_time - ts).total_seconds() < 3600  # Keep last hour
        }
        server_logger.debug(f"Cleaned connection attempts. Current size: {len(self.connection_attempts)}")
        #Save blacklist asynchronously during cleanup
        asyncio.create_task(self.save_blacklist())
        asyncio.create_task(self.clean_expired_blacklist_entries())  # Clean expired blacklist entries

    async def get_dynamic_threshold(self, client_ip):
        """Calculate a dynamic threshold based on historical blacklist data."""
        # CHANGED: Load history and merge with blacklist
        history = await self.load_blacklist_history("blacklist_history.json")
        combined_data = {**self.blacklist, **history}  # Merge active blacklist and history
        if not combined_data:
            return self.base_blacklist_threshold  # Fallback if no data

        # CHANGED: IP-specific adjustment based on combined data
        if client_ip in combined_data:
            info = combined_data[client_ip]
            if info["attempts"] < self.base_blacklist_threshold:
                return self.base_blacklist_threshold + 2
            elif info["attempts"] > self.base_blacklist_threshold * 2:
                return max(self.base_blacklist_threshold - 1, 3)

        # CHANGED: Weighted average prioritizing recent entries
        current_time = datetime.now()
        weighted_sum = 0
        total_weight = 0
        for ip, info in combined_data.items():
            age_hours = (current_time - info["timestamp"]).total_seconds() / 3600
            weight = max(1.0, 10.0 - age_hours / 24)  # Higher weight for recent entries (within 24h)
            weighted_sum += info["attempts"] * weight
            total_weight += weight
        weighted_avg = weighted_sum / total_weight if total_weight > 0 else self.base_blacklist_threshold
        return max(self.base_blacklist_threshold, int(weighted_avg))

    async def generate_blacklist_report(self):
        """Generate a report of blacklisted IPs with metadata."""
        async with self.blacklist_lock:
            report = [
                f"Blacklist Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total IPs: {len(self.blacklist)}",
                "-" * 50
            ]
            for ip, info in self.blacklist.items():
                time_diff_hours = (datetime.now() - info["timestamp"]).total_seconds() / 3600
                expiry_status = ("Permanent" if info["reason"] in self.permanent_reasons else
                                f"Expires in {self.blacklist_expiry_hours - time_diff_hours:.1f} hours")
                report.append(
                    f"IP: {ip}\n"
                    f"  Timestamp: {info['timestamp']}\n"
                    f"  Attempts: {info['attempts']}\n"
                    f"  Reason: {info['reason']}\n"
                    f"  Status: {expiry_status}"
                )
            report_str = "\n".join(report)
            server_logger.info(f"Generated blacklist report:\n{report_str}")
            # Optionally save to a file
            report_file = f"blacklist_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            async with aiofiles.open(report_file, 'w') as f:
                await f.write(report_str)
            server_logger.debug(f"Blacklist report saved to {report_file}")
            return report_str
    
    #Admin methods from server26.py
    async def reset_model(self, admin_token):
        server_logger.info(f"Model reset requested with admin token {admin_token}")
        if not self.auth_manager.is_admin(self.auth_manager.sessions[admin_token]["username"]):
            server_logger.warning(f"Model reset denied for token {admin_token}: Not an admin")
            return False
        async with model_lock:
            self.model, self.optimizer_state = self.initialize_model()
            server_logger.info(f"Model reset by admin {self.auth_manager.sessions[admin_token]['username']}")
        return True

    async def admin_get_logs(self, admin_token, log_type):
        server_logger.info(f"Log retrieval requested for {log_type} with admin token {admin_token}")
        if not self.auth_manager.is_admin(self.auth_manager.sessions[admin_token]["username"]):
            server_logger.warning(f"Log retrieval denied for token {admin_token}: Not an admin")
            return None
        safe_log_type = os.path.basename(log_type).replace("\\", "").replace("/", "")
        log_aliases = {
            "auth": "auth.log",
            "audit": "audit.log",
            "mfa": "mfa.log",
            "server": "server_logs.log",
            "server_logs": "server_logs.log",
            "firewall": "firewall.log",
            "device_fingerprint": "device_fingerprint.log",
            "token_manager": "token_manager.log",
            "security_engine": "Security_engine.log",
            "master": "master_log.log",
            "master_log": "master_log.log",
        }
        log_file_name = log_aliases.get(safe_log_type.lower(), safe_log_type)
        if not log_file_name.endswith(".log"):
            log_file_name = f"{log_file_name}.log"
        log_file = os.path.join("logs", log_file_name)
        if os.path.exists(log_file):
            async with aiofiles.open(log_file, 'r') as f:
                logs = await f.read()
                server_logger.info(f"Logs retrieved for {log_type} by admin {self.auth_manager.sessions[admin_token]['username']}")
                return logs
        server_logger.warning(f"Log file {log_file} not found")
        return "Log file not found"
    # def fine_tune_model(self, dataset_path):
    #     server_logger.info(f"Starting fine-tuning on {dataset_path} for {self.epochs} epochs")
    #     dataset = CustomDataset(dataset_path)
    #     dataloader = DataLoader(dataset, batch_size=32, shuffle=True, pin_memory=torch.cuda.is_available())
    #     optimizer = optim.AdamW(self.model.parameters(), lr=self.lr)
    #     scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.epochs)
    #     criterion = nn.CrossEntropyLoss()
    #     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    #     self.model.to(device)
    #     self.model.train()
    #     for epoch in range(self.epochs):
    #         total_loss = 0
    #         for features, labels in dataloader:
    #             features, labels = features.to(device), labels.to(device)
    #             optimizer.zero_grad()
    #             outputs = self.model(features)
    #             loss = criterion(outputs, labels)
    #             loss.backward()
    #             torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
    #             optimizer.step()
    #             total_loss += loss.item()
    #         avg_loss = total_loss / len(dataloader)
    #         server_logger.info(f"Fine-tuning Epoch {epoch+1}/{self.epochs}, Loss: {avg_loss:.4f}")
    #         scheduler.step()
    def fine_tune_model(self, dataset_path, epochs=10, lr=1e-5, test_dataset=None):
        server_logger.info(f"Starting fine-tuning on {dataset_path} for {epochs} epochs with lr={lr}")
        # Use test_dataset for training to align with client's evaluation dataset
        train_dataset = test_dataset if test_dataset is not None else CustomDataset(dataset_path)
        dataloader = DataLoader(train_dataset, batch_size=32, shuffle=True, pin_memory=torch.cuda.is_available())

        # Match client's optimizer settings
        if hasattr(self, 'optimizer_state') and self.optimizer_state is not None:
            optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
            try:
                optimizer.load_state_dict(self.optimizer_state)
                server_logger.info("Loaded client optimizer state for fine-tuning")
            except Exception as e:
                server_logger.warning(f"Failed to load optimizer state: {e}. Initializing new optimizer.")
                optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        else:
            optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
            server_logger.info("Initialized new optimizer as no prior state exists")

        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        criterion = nn.CrossEntropyLoss()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(device)

        # Evaluate on test_dataset
        self.model.eval()
        with torch.no_grad():
            pre_metrics = self.evaluate_model(test_dataset)
        server_logger.info(f"Pre-fine-tuning metrics: {pre_metrics}")

        # Fine-tuning loop
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for features, labels in dataloader:
                features, labels = features.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = self.model(features)
                loss = criterion(outputs, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(dataloader)
            server_logger.info(f"Fine-tuning Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
            scheduler.step()

        self.model.eval()
        with torch.no_grad():
            post_metrics = self.evaluate_model(test_dataset)
        server_logger.info(f"Post-fine-tuning metrics: {post_metrics}")

        self.optimizer_state = optimizer.state_dict()

    def initialize_model(self):
        if os.path.exists(global_model_file):
            file_path = global_model_file
            server_logger.info(f"Global model file found at '{global_model_file}'.")
        else:
            file_path = model_path
            server_logger.info(f"Using fallback file '{model_path}' for first-time initialization.")
        extension = os.path.splitext(file_path)[1]
        server_logger.info(f"Initializing model from {file_path} with extension {extension}")
        if extension in [".pth", ".pt"]:
            checkpoint = torch.load(file_path, map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            if isinstance(checkpoint, dict):
                if "model_state_dict" in checkpoint and "config" in checkpoint:
                    self.model_config = checkpoint["config"]
                    server_logger.info(f"Loaded model config: {self.model_config}")
                    if self.model_config.get("model_type") == "HybridModel":
                        if not verify_config_integrity(self.model_config):
                            raise ValueError("Config integrity check failed.")
                        model = create_hybrid_model(self.model_config)
                        model.load_state_dict(checkpoint["model_state_dict"], strict=False)
                    else:
                        model = create_model_from_state_dict(checkpoint["model_state_dict"])
                    optimizer = optim.AdamW(model.parameters(), lr=self.lr)
                    if "optimizer_state_dict" in checkpoint:
                        self.optimizer_state = checkpoint["optimizer_state_dict"]
                        if isinstance(self.optimizer_state, tuple):
                            self.optimizer_state = self.optimizer_state[0]
                        try:
                            optimizer.load_state_dict(self.optimizer_state)
                            server_logger.info("Optimizer state loaded successfully.")
                        except ValueError as e:
                            server_logger.warning(f"Optimizer state mismatch: {e}. Resetting.")
                            optimizer = optim.AdamW(model.parameters(), lr=self.lr)
                # elif "model_state_dict" in checkpoint:
                #     model = create_model_from_state_dict(checkpoint["model_state_dict"])
                #     model.load_state_dict(checkpoint["model_state_dict"], strict=False)
                #     self.optimizer_state = None
                # else:
                #     model = create_model_from_state_dict(checkpoint)
                #     model.load_state_dict(checkpoint, strict=False)
                #     self.optimizer_state = None
            else:
                model = checkpoint
                self.optimizer_state = None
        elif extension == ".pkl":
            try:
                with open(file_path, "rb") as f:
                    model = pickle.load(f)
                self.optimizer_state = None
            except Exception as e:
                server_logger.error(f"Error with pickle: {e}. Trying joblib...")
                model = joblib.load(file_path)
                self.optimizer_state = None
        elif extension == ".h5":
            model = tf_load_model(file_path)
            self.optimizer_state = None
        else:
            raise ValueError(f"Unsupported model format: {extension}")
        server_logger.info(f"Global model initialized from {file_path}.")
        if file_path == model_path:
            server_logger.info("Saving model to global model folder.")
            self.model = model
            self.save_model()
        return model, self.optimizer_state

    def save_model(self):
        if not self.model:
            server_logger.error("ERROR: self.model is None. Cannot save!")
            return
        ext = os.path.splitext(global_model_file)[1]
        versioned_path = os.path.join(model_versions_path, f"model_v{self.model_version}{ext}")
        server_logger.info(f"Saving model version {self.model_version} to {global_model_file} and {versioned_path}")
        if(self.optimizer_state is None):
            server_logger.info(f"Optimizer is {self.optimizer_state}")
        if ext in [".pth", ".pt"]:
            checkpoint = {"model_state_dict": self.model.state_dict(), "optimizer_state_dict": self.optimizer_state, "config": self.model_config}
            with open(global_model_file, "wb") as f:
                torch.save(checkpoint, f)
            with open(versioned_path, "wb") as f:
                torch.save(checkpoint, f)
        elif ext == ".h5":
            self.model.save(global_model_file)
            self.model.save(versioned_path)
        else:
            with open(global_model_file, "wb") as f:
                pickle.dump(self.model, f)
            with open(versioned_path, "wb") as f:
                pickle.dump(self.model, f)
        server_logger.info(f"Model saved as version {self.model_version}.")

    async def log_connection_attempt(self, reader, writer):
        """Log connection attempts and use blacklist metadata for decisions."""
        try:
            addr = writer.get_extra_info('peername')
            client_ip = addr[0] if addr else "unknown"
        except Exception as e:
            client_ip = "unknown"
            server_logger.error(f"Failed to get peername: {e}")
            return
        
        server_logger.info(f"Connection attempt from {client_ip}")
        server_logger.debug(f"New connection established from {addr}")

        if not await rate_limit(client_ip):
            server_logger.warning(f"Connection blocked for {client_ip}: Rate limit exceeded")
            writer.write(b"ERROR: Rate limit exceeded\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            log_client_event(client_ip, "BLOCKED", "Rate limit exceeded")
            return
        if not await check_geo_location(client_ip):
            server_logger.warning(f"Connection blocked for {client_ip}: Geo-location restricted")
            writer.write(b"ERROR: Geo-location restricted\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            log_client_event(client_ip, "BLOCKED", "Geo-location restricted")
            return

        # Check blacklist with metadata
        if client_ip in self.blacklist:
            info = self.blacklist[client_ip]
            time_diff_hours = (datetime.now() - info["timestamp"]).total_seconds() / 3600
            if info["reason"] not in self.permanent_reasons and time_diff_hours > self.blacklist_expiry_hours:
                server_logger.info(f"Blacklist entry for {client_ip} expired (added at {info['timestamp']}); removing.")
                async with self.blacklist_lock:
                    del self.blacklist[client_ip]
                    self.blacklist_changed = True
                await self.save_blacklist()
            else:
                server_logger.info(f"Blocked connection from {client_ip}: "
                    f"Blacklisted at {info['timestamp']}, "
                    f"Attempts: {info['attempts']}, "
                    f"Reason: {info['reason']}"
                )

                writer.write(f"ERROR: IP blacklisted at {info['timestamp']} for {info['reason']}\n".encode("utf-8"))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                log_client_event(client_ip, "BLOCKED", f"Reason: {info['reason']}, Attempts: {info['attempts']}")
                return

        # Log every attempt
        server_logger.debug(f"Connection attempt from {addr} to server {self.host}:{self.port}")

        # Dynamic threshold based on metadata
        threshold =await self.get_dynamic_threshold(client_ip)
        # Track for stealth scan detection
        current_time = datetime.now()
        if client_ip in self.connection_attempts:
            count, last_time = self.connection_attempts[client_ip]
            time_diff = (current_time - last_time).total_seconds()
            if time_diff < 1:
                count += 1
                if count > threshold:
                    reason = f"Suspected stealth scan: {count} attempts in {time_diff:.2f}s (threshold: {threshold})"
                    server_logger.warning(f"Blacklisting {client_ip}: {reason}")
                    async with self.blacklist_lock:
                        self.blacklist[client_ip] = {
                            "timestamp": current_time,
                            "attempts": count,
                            "reason": reason
                        }
                        self.blacklist_changed = True
                    await self.save_blacklist()
                    writer.write(f"ERROR: IP blocked due to {reason}\n".encode("utf-8"))
                    await writer.drain()
                    try:
                        writer.close()
                        # await writer.wait_closed()
                    except ssl.SSLError as e:
                        if "APPLICATION_DATA_AFTER_CLOSE_NOTIFY" in str(e):
                            server_logger.warning(f"Ignoring harmless SSL error: {e}")
                        else:
                            server_logger.warning(f"Ignoring harmed SSL error: {e}")
                            return
                    log_client_event(client_ip, "BLACKLISTED", reason)
                    return
            else:
                count = 1  # Reset if time gap is significant
        else:
            count = 1
        self.connection_attempts[client_ip] = (count, current_time)

        # Proceed to handle the connection
        # CHANGED: Added log before proceeding to handle_client
        server_logger.debug(f"Proceeding to handle client request from {addr}")
        await self.handle_client(reader, writer)

        

    # async def handle_client(self, reader, writer):
    #     addr = writer.get_extra_info('peername')
    #     client_ip = addr[0] if addr else "unknown"
    #     logger.info(f"Connection from {addr} to server {self.host}:{self.port}") 
    #     # ✅ FIX: Keep-alive messages to prevent timeout disconnections
    #     async def send_keep_alive():
    #         """Send keep-alive messages while waiting for OTP input."""
    #         try:
    #             while True:
    #                 await asyncio.sleep(10)
    #                 writer.write(b"KEEP_ALIVE\n")
    #                 await writer.drain()
    #                 logger.debug(f"Sent keep-alive to {client_ip}")
    #         except Exception as e:
    #             logger.warning(f"Keep-alive failed: {e}")
    #     # try:
    #     #     # CHANGED: Added debug log before reading data
    #     #     logger.debug(f"Awaiting data from {addr}")
    #     #     data = await asyncio.wait_for(reader.read(1024), timeout=300)  # Set timeout
    #     #     logger.debug(f"Received data from {addr}: {data}")
    #     try:
    #     # ✅ START CHANGE: Send initial keep-alive message to prevent idle timeout
    #         logger.debug("Send initial keep-alive message to prevent idle timeout")
    #         keep_alive_task = asyncio.create_task(send_keep_alive())
    #         data = await asyncio.wait_for(reader.read(1024), timeout=300)  

    #         keep_alive_task.cancel

    #         if not data:
    #             logger.warning(f"No data received from {client_ip}, closing connection")
    #             # writer.close()
    #             # await writer.wait_closed()
    #             return
    #         logger.debug(f"Received {len(data)} bytes from {addr}: {data!r}")    
    #         try:
    #             message = data.decode("utf-8", errors="replace").strip()
    #             parts = message.split("|")
    #             logger.info(f"Decoded message from {addr}: {message}")
    #         except UnicodeDecodeError as ude:
    #             error_msg = "ERROR: Invalid command encoding. Please send the command in UTF-8 text format.\n"
    #             writer.write(error_msg.encode("utf-8", errors="replace"))
    #             await writer.drain()
    #             logger.error(f"Decoding error from client {addr}: {ude}: raw data: {data!r}")  
    #             return
    #         #Authentication from server26.py
    #         if parts[0] == "AUTH_USERNAME":
    #             username, password = parts[1], parts[2]
    #             logger.info(f"Authentication request for {username} from {client_ip}")
    #             username, email = await self.auth_manager.authenticate_step1(username, password, client_ip)
    #             if not username:
    #                 logger.warning(f"Authentication failed for {username} at {client_ip}")
    #                 writer.write(b"ERROR: Invalid credentials\n")
    #                 await writer.drain()
    #                 return  # ✅ Return only if authentication fails

    #             else:
    #                 await self.auth_manager.authenticate_step2(username, email, client_ip)
    #                 writer.write(f"OTP_SENT|{email}\n".encode())
    #                 logger.info(f"OTP sent to {email} for {username} at {client_ip}")
    #             await writer.drain()
                
    #         # ✅ FIX: Ensure server waits for OTP input after sending OTP
    #         try:
    #             logger.info(f"Waiting for client OTP input (Timeout: 300s)...")
                
    #             keep_alive_task = asyncio.create_task(send_keep_alive())
    #             # ✅ FIX: Wait for OTP input (now properly logged)
    #             otp_data = await asyncio.wait_for(reader.read(1024), timeout=300)
    #             # ✅ Stop keep-alive task when OTP is received
    #             keep_alive_task.cancel()
    #             if not otp_data:
    #                 logger.warning(f"No OTP received from {client_ip}, closing connection.")
    #                 return
    #             # ✅ Process OTP verification
    #             message = otp_data.decode("utf-8", errors="replace").strip()
    #             parts = message.split("|")
    #             logger.info(f"Received OTP verification request from {client_ip}: {message}")
                    
    #         except asyncio.TimeoutError:
    #             logger.warning(f"Timeout after 300s waiting for OTP from {client_ip}")
    #             writer.write(b"ERROR: Timeout waiting for OTP\n")
    #             await writer.drain()
    #         except Exception as e:
    #             logger.error(f"Unexpected error handling OTP for {client_ip}: {e}")

    #         if parts[0] == "VERIFY_OTP":
    #                     username, otp, totp_code = parts[1], parts[2], parts[3] if len(parts) > 3 else None
    #                     logger.info(f"OTP verification for {username} from {client_ip}")
    #                     logger.debug(f"Calling authenticate_step3 with OTP={otp}, TOTP={totp_code}")
    #                     result = await self.auth_manager.authenticate_step3(username, client_ip, otp, totp_code)
    #                     if result:
    #                         token, refresh_token, hmac_key, admin_token = result
    #                         response = f"TOKEN_ISSUED|{token}|{refresh_token}|{hmac_key}"
    #                         if admin_token:
    #                             response += f"|{admin_token}"
    #                         writer.write(response.encode())
    #                         logger.info(f"Tokens issued to {username} at {client_ip}: Token {token}, Admin Token {admin_token if admin_token else 'N/A'}")
    #                     else:
    #                         logger.warning(f"OTP/TOTP verification failed for {username} at {client_ip}")
    #                         writer.write(b"ERROR: OTP/TOTP verification failed\n")
                        
    #                     await writer.drain()
    #                     return
            
    #         elif parts[0] == "REFRESH_TOKEN":
    #             refresh_token = parts[1]
    #             logger.info(f"Token refresh request from {client_ip} with {refresh_token}")
    #             result = await self.auth_manager.refresh_token(refresh_token, client_ip)
    #             if result:
    #                 new_token, hmac_key, admin_token = result
    #                 response = f"TOKEN_REFRESHED|{new_token}|{hmac_key}"
    #                 if admin_token:
    #                     response += f"|{admin_token}"
    #                 writer.write(response.encode())
    #                 logger.info(f"Token refreshed for {client_ip}: New Token {new_token}, Admin Token {admin_token if admin_token else 'N/A'}")
    #             else:
    #                 logger.warning(f"Token refresh failed for {client_ip}")
    #                 writer.write(b"ERROR: Refresh token invalid\n")
    #             await writer.drain()
    #             return

    #         elif len(parts) >= 4:
    #             token, request, signature, _ = parts[0], parts[1], parts[2], parts[3:]
    #             request_data = "|".join(parts[1:])
    #             is_admin_action = request.startswith("ADMIN_")
    #             logger.info(f"Processing request from {client_ip}: {request}, Admin: {is_admin_action}")
    #             verification = await self.auth_manager.verify_request(token, client_ip, request_data, signature, is_admin_action)
    #             if verification is True:
    #                 if request == "SEND_UPDATE":
    #                     await self.receive_update(reader, writer, client_ip, token)
    #                     log_client_event(client_ip, "SEND_UPDATE", "Client sent model update")
    #                 elif request == "GET_MODEL":
    #                     await self.send_model(writer)
    #                     log_client_event(client_ip, "GET_MODEL", "Client requested model")
    #                 elif request == "PING":
    #                     writer.write(b"PING\n")
    #                     await writer.drain()
    #                     log_client_event(client_ip, "PING", "Client pinged the server")
    #                 elif request == "ADMIN_BLOCK_IP" and len(parts) == 5:
    #                     ip_to_block = parts[3]
    #                     logger.info(f"Admin block IP {ip_to_block} requested from {client_ip}")
    #                     if await self.auth_manager.admin_block_ip(token, ip_to_block):
    #                         async with self.blacklist_lock:
    #                             self.blacklist[ip_to_block] = {"timestamp": datetime.now(), "attempts": 0, "reason": "Admin block"}
    #                             self.blacklist_changed = True
    #                         await self.save_blacklist()
    #                         writer.write(b"IP_BLOCKED\n")
    #                         logger.info(f"IP {ip_to_block} blocked by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin block IP failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required\n")
    #                 elif request == "ADMIN_ADD_USER" and len(parts) == 7:
    #                     username, email, password, phone = parts[3:]
    #                     logger.info(f"Admin add user {username} requested from {client_ip}")
    #                     if await self.auth_manager.admin_add_user(token, username, email, password, phone):
    #                         writer.write(b"USER_ADDED\n")
    #                         logger.info(f"User {username} added by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin add user failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required or duplicate user\n")
    #                 elif request == "ADMIN_DELETE_USER" and len(parts) == 5:
    #                     username = parts[3]
    #                     logger.info(f"Admin delete user {username} requested from {client_ip}")
    #                     if await self.auth_manager.admin_delete_user(token, username):
    #                         writer.write(b"USER_DELETED\n")
    #                         logger.info(f"User {username} deleted by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin delete user failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required or user not found\n")
    #                 elif request == "ADMIN_LIST_SESSIONS":
    #                     logger.info(f"Admin list sessions requested from {client_ip}")
    #                     sessions = await self.auth_manager.admin_list_sessions(token)
    #                     if sessions is not None:
    #                         writer.write(f"SESSIONS|{json.dumps(sessions)}\n".encode())
    #                         logger.info(f"Sessions listed by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin list sessions failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required\n")
    #                 elif request == "ADMIN_TERMINATE_SESSION" and len(parts) == 5:
    #                     target_token = parts[3]
    #                     logger.info(f"Admin terminate session {target_token} requested from {client_ip}")
    #                     if await self.auth_manager.admin_terminate_session(token, target_token):
    #                         writer.write(b"SESSION_TERMINATED\n")
    #                         logger.info(f"Session {target_token} terminated by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin terminate session failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required or session not found\n")
    #                 elif request == "ADMIN_RESET_MODEL":
    #                     logger.info(f"Admin reset model requested from {client_ip}")
    #                     if await self.reset_model(token):
    #                         writer.write(b"MODEL_RESET\n")
    #                         logger.info(f"Model reset by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin reset model failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required\n")
    #                 elif request == "ADMIN_GET_LOGS" and len(parts) == 5:
    #                     log_type = parts[3]
    #                     logger.info(f"Admin get logs {log_type} requested from {client_ip}")
    #                     logs = await self.admin_get_logs(token, log_type)
    #                     if logs:
    #                         writer.write(f"LOGS|{logs}\n".encode())
    #                         logger.info(f"Logs {log_type} retrieved by admin from {client_ip}")
    #                     else:
    #                         logger.warning(f"Admin get logs failed from {client_ip}")
    #                         writer.write(b"ERROR: Admin privilege required or log not found\n")
    #                 else:
    #                     logger.warning(f"Invalid request from {client_ip}: {request}")
    #                     writer.write(b"INVALID_REQUEST\n")
    #             elif verification == "REAUTH_REQUIRED":
    #                 logger.info(f"Re-authentication required for {client_ip}")
    #                 writer.write(b"REAUTH_REQUIRED\n")
    #             else:
    #                 logger.warning(f"Authentication failed for request from {client_ip}")
    #                 writer.write(b"ERROR: Authentication failed\n")
    #             await writer.drain()
    #         else:
    #             logger.warning(f"Invalid request format from {client_ip}: {message}")
    #             writer.write(b"ERROR: Invalid request format\n")
    #             await writer.drain()
    #     except asyncio.TimeoutError:
    #         logger.warning(f"Timeout after 300s waiting for data from {client_ip}")
    #         writer.write(b"ERROR: Timeout waiting for response\n")
    #         await writer.drain()
    #     except Exception as e:
    #         logger.error(f"Error handling client {addr}: {e}")
    #     finally:
    #         # Graceful shutdown
    #         keep_alive_task.cancel()
    #         try:
                
    #             writer.close()
    #             await asyncio.sleep(1)
    #             await asyncio.wait_for(writer.wait_closed(), timeout=10)
    #             # await writer.wait_closed()
    #             logger.debug(f"Connection to {addr} closed successfully")
    #         except ssl.SSLError as ssl_err:
    #             logger.warning(f"SSL shutdown error with {client_ip}: {ssl_err}")
    #         except ConnectionResetError:
    #             logger.warning(f"Connection reset by client {client_ip}, handling gracefully.")
    #         except asyncio.TimeoutError:
    #             logger.warning(f"Forced closing connection to {addr} after timeout")
    #         except Exception as e:
    #             logger.error(f"Unexpected error closing connection: {e}")
            

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        client_ip = addr[0] if addr else "unknown"
        server_logger.info(f"Connection from {addr} to server {self.host}:{self.port}")

        async def send_keep_alive():
            try:
                while True:
                    await asyncio.sleep(10)
                    writer.write(b"KEEP_ALIVE\n")
                    await writer.drain()
                    server_logger.debug(f"Sent keep-alive to {client_ip}")
            except Exception as e:
                server_logger.warning(f"Keep-alive failed: {e}")

        keep_alive_task = asyncio.create_task(send_keep_alive())
        
        try:
            # CHANGED: Keep the connection open for multiple requests instead of closing after one
            while True:
                data = await asyncio.wait_for(reader.read(1024), timeout=300)
                if not data:
                    server_logger.info(f"Client {client_ip} closed connection")
                    break
                
                message = data.decode("utf-8", errors="replace").strip()
                parts = message.split("|")
                server_logger.info(f"Decoded message from {addr}: {message}")

                if parts[0] == "AUTH_USERNAME":
                    username, password = parts[1], parts[2]
                    server_logger.info(f"Authentication request for {username} from {client_ip}")
                    username, email = await self.auth_manager.authenticate_step1(username, password, client_ip)
                    if not (username or email):
                        server_logger.warning(f"Authentication failed for {username} at {client_ip}")
                        writer.write(b"ERROR: Invalid credentials\n")
                    else:
                        await self.auth_manager.authenticate_step2(username, email, client_ip)
                        writer.write(f"OTP_SENT|{email}\n".encode())
                        server_logger.info(f"OTP sent to {email} for {username} at {client_ip}")
                    await writer.drain()

                elif parts[0] == "VERIFY_OTP":
                    username, otp, totp_code = parts[1], parts[2], parts[3] if len(parts) > 3 else None
                    server_logger.info(f"OTP verification for {username} from {client_ip}")
                    server_logger.debug(f"Calling authenticate_step3 with OTP={otp}, TOTP={totp_code}")
                    result = await self.auth_manager.authenticate_step3(username, client_ip, otp, totp_code)
                    if result:
                        token, refresh_token, hmac_key, admin_token = result
                        response = f"TOKEN_ISSUED|{token}|{refresh_token}|{hmac_key}"
                        if admin_token:
                            response += f"|{admin_token}"
                        writer.write(response.encode())
                        server_logger.info(f"Tokens issued to {username} at {client_ip}: Token {token}, Admin Token {admin_token if admin_token else 'N/A'}")
                    else:
                        server_logger.warning(f"OTP/TOTP verification failed for {username} at {client_ip}")
                        writer.write(b"ERROR: OTP/TOTP verification failed\n")
                    await writer.drain()

                # CHANGED: Added EXIT command handling to terminate session gracefully
                elif parts[0] == "EXIT":
                    server_logger.info(f"Client {client_ip} requested session termination")
                    break

                elif parts[0] == "REFRESH_TOKEN":
                    refresh_token = parts[1]
                    server_logger.info(f"Token refresh request from {client_ip} with {refresh_token}")
                    result = await self.auth_manager.refresh_token(refresh_token, client_ip)
                    if result:
                        new_token, hmac_key, admin_token = result
                        response = f"TOKEN_REFRESHED|{new_token}|{hmac_key}"
                        if admin_token:
                            response += f"|{admin_token}"
                        writer.write(response.encode())
                        server_logger.info(f"Token refreshed for {client_ip}: New Token {new_token}, Admin Token {admin_token if admin_token else 'N/A'}")
                    else:
                        server_logger.warning(f"Token refresh failed for {client_ip}")
                        writer.write(b"ERROR: Refresh token invalid\n")
                    await writer.drain()

                elif len(parts) >= 3:
                    token, request, signature = parts[0], parts[1], parts[2]
                    request_args = parts[3:]
                    request_data = "|".join([request] + request_args)
                    is_admin_action = request.startswith("ADMIN_")
                    server_logger.debug(f"Logger type before processing log: {type(server_logger)}")
                    server_logger.info(f"Processing request from {client_ip}: {request}, Admin: {is_admin_action}")
                    verification = await self.auth_manager.verify_request(token, client_ip, request_data, signature, is_admin_action)
                    server_logger.info(f"Verification result {verification}")
                    server_logger.debug(f"Logger type before processing log: {type(server_logger)}")
                    server_logger.info(f"Verification result {verification}")
                    if verification is True:
                        if request == "SEND_UPDATE":
                            writer.write(b"READY_FOR_UPDATE\n")
                            await writer.drain()
                            await self.receive_update(reader, writer, client_ip)
                            log_client_event(client_ip, "SEND_UPDATE", "Client sent model update")
                        elif request == "GET_MODEL":
                            await self.send_model(writer)
                            log_client_event(client_ip, "GET_MODEL", "Client requested model")
                        elif request == "PING":
                            writer.write(b"PING\n")
                            await writer.drain()
                            log_client_event(client_ip, "PING", "Client pinged the server")
                        elif request == "EXIT":
                            server_logger.info(f"Authenticated client {client_ip} requested session termination")
                            break
                        elif request == "ADMIN_BLOCK_IP" and len(parts) == 4:
                            ip_to_block = request_args[0]
                            server_logger.debug(f"server_logger type: {type(server_logger)}")
                            server_logger.info(f"Admin block IP {ip_to_block} requested from {client_ip}")
                            if await self.auth_manager.admin_block_ip(token, ip_to_block):
                                async with self.blacklist_lock:
                                    self.blacklist[ip_to_block] = {"timestamp": datetime.now(), "attempts": 0, "reason": "Admin block"}
                                    self.blacklist_changed = True
                                await self.save_blacklist()
                                writer.write(b"IP_BLOCKED\n")
                                server_logger.debug(f"server_logger type: {type(server_logger)}")
                                server_logger.info(f"IP {ip_to_block} blocked by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin block IP failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required\n")
                        elif request == "ADMIN_ADD_USER" and len(parts) == 7:
                            username, email, password, phone = parts[3:]
                            server_logger.info(f"Admin add user {username} requested from {client_ip}")
                            if await self.auth_manager.admin_add_user(token, username, email, password, phone):
                                writer.write(b"USER_ADDED\n")
                                server_logger.info(f"User {username} added by admin from {client_ip}")
                            else:
                                reason = self.auth_manager.last_admin_error or "user registration failed"
                                server_logger.warning(f"Admin add user failed from {client_ip}: {reason}")
                                writer.write(f"ERROR: {reason}\n".encode())
                        elif request == "ADMIN_DELETE_USER" and len(parts) == 4:
                            username = request_args[0]
                            server_logger.info(f"Admin delete user {username} requested from {client_ip}")
                            if await self.auth_manager.admin_delete_user(token, username):
                                writer.write(b"USER_DELETED\n")
                                server_logger.info(f"User {username} deleted by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin delete user failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required or user not found\n")
                        elif request == "ADMIN_LIST_SESSIONS":
                            server_logger.info(f"Admin list sessions requested from {client_ip}")
                            sessions = await self.auth_manager.admin_list_sessions(token)
                            if sessions is not None:
                                writer.write(f"SESSIONS|{json.dumps(sessions)}\n".encode())
                                server_logger.info(f"Sessions listed by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin list sessions failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required\n")
                        elif request == "ADMIN_TERMINATE_SESSION" and len(parts) == 4:
                            target_token = request_args[0]
                            server_logger.info(f"Admin terminate session {target_token} requested from {client_ip}")
                            if await self.auth_manager.admin_terminate_session(token, target_token):
                                writer.write(b"SESSION_TERMINATED\n")
                                server_logger.info(f"Session {target_token} terminated by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin terminate session failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required or session not found\n")
                        elif request == "ADMIN_RESET_MODEL":
                            server_logger.info(f"Admin reset model requested from {client_ip}")
                            if await self.reset_model(token):
                                writer.write(b"MODEL_RESET\n")
                                server_logger.info(f"Model reset by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin reset model failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required\n")
                        elif request == "ADMIN_GET_LOGS" and len(parts) == 4:
                            log_type = request_args[0]
                            server_logger.info(f"Admin get logs {log_type} requested from {client_ip}")
                            logs = await self.admin_get_logs(token, log_type)
                            if logs:
                                writer.write(f"LOGS|{logs}\n".encode())
                                server_logger.info(f"Logs {log_type} retrieved by admin from {client_ip}")
                            else:
                                server_logger.warning(f"Admin get logs failed from {client_ip}")
                                writer.write(b"ERROR: Admin privilege required or log not found\n")
                        else:
                            server_logger.warning(f"Invalid request from {client_ip}: {request}")
                            writer.write(b"INVALID_REQUEST\n")
                    elif verification == "REAUTH_REQUIRED":
                        server_logger.info(f"Re-authentication required for {client_ip}")
                        writer.write(b"REAUTH_REQUIRED\n")
                    else:
                        server_logger.warning(f"Authentication failed for request from {client_ip}")
                        writer.write(b"ERROR: Authentication failed\n")
                    await writer.drain()
                else:
                    server_logger.warning(f"Invalid request format from {client_ip}: {message}")
                    writer.write(b"ERROR: Invalid request format\n")
                    await writer.drain()

        except asyncio.TimeoutError:
            server_logger.warning(f"Timeout after 300s waiting for data from {client_ip}")
            writer.write(b"ERROR: Timeout waiting for response\n")
            await writer.drain()
        except Exception as e:
            server_logger.error(f"Error handling client {addr}: {e}")
            master_error(f"Error handling client {addr}: {e}")
        
        finally:
            keep_alive_task.cancel()
            try:
                writer.close()
                await writer.wait_closed()
                server_logger.debug(f"Connection to {addr} closed successfully")
            # CHANGED: Improved SSL error handling to ignore benign shutdown errors
            except ssl.SSLError as ssl_err:
                if "APPLICATION_DATA_AFTER_CLOSE_NOTIFY" in str(ssl_err):
                    server_logger.debug(f"Ignored benign SSL shutdown warning with {client_ip}: {ssl_err}")
                else:
                    server_logger.warning(f"SSL shutdown error with {client_ip}: {ssl_err}")
            except Exception as e:
                server_logger.error(f"Unexpected error closing connection: {e}")
                master_error(f"Unexpected error closing connection: {e}")


    async def receive_update(self, reader, writer, client_ip):
        try:
            header_line = await reader.readline()
            server_logger.debug(f"Received header bytes from {client_ip}: {header_line}")
            header = header_line.decode("utf-8", errors="replace").strip()
            if not header_line:
                server_logger.warning(f"Empty header received from {client_ip}")  # Add this line
                return
            server_logger.info(f"Decoded header from {client_ip}: {header}")
            if not header.startswith("TYPE:"):
                error_msg = "ERROR: Missing or invalid header. Expected header format: TYPE:<extension>.\n"
                writer.write(error_msg.encode("utf-8", errors="replace"))
                await writer.drain()
                server_logger.error(f"Invalid header from client {client_ip}: {header}")
                return
            header_parts = dict(
                part.split(":", 1) for part in header.split("|") if ":" in part
            )
            ext = header_parts.get("TYPE")
            payload_size = int(header_parts["SIZE"]) if "SIZE" in header_parts else None
            if not ext:
                raise ValueError("Missing model extension in update header")
            server_logger.info(f"Receiving update with model type: {ext} from {client_ip}")
            
            if payload_size is None:
                raise ValueError("Missing SIZE in update header")
            data = await reader.readexactly(payload_size)
            server_logger.info(f"Total data size received from {client_ip}: {len(data)} bytes")
            master_info(f"Total data size received from {client_ip}: {len(data)} bytes")
            server_logger.debug(f"Raw data sample from {client_ip}: {data[:100]!r}... (total {len(data)} bytes)")  
            decompressed_data = zlib.decompress(data)
            server_logger.info(f"Successfully decompressed data from {client_ip}")

            # CHANGED: Save client update temporarily for initialization
            # WHERE: Before processing the update
            client_model_filename = f"client_model_{client_ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            client_model_path = os.path.join(client_models_dir, client_model_filename)
            with open(client_model_path, "wb") as f:
                f.write(decompressed_data)

            # CHANGED: Backup current global model state for fallback
            # WHERE: Before attempting to initialize from the update
            try:
                self.pre_update_state = {k: v.clone() for k, v in self.model.state_dict().items()}
                self.pre_update_config = self.model_config.copy() if hasattr(self, "model_config") else {}
                self.pre_update_optimizer_state = copy.deepcopy(self.optimizer_state)
                server_logger.debug(f"Fully backed up global model state (parameters, config, optimizer) before update from {client_ip}")
            except Exception as e:
                server_logger.warning(f"Failed to fully backup global model state: {e}. Proceeding with partial or no backup.")
            # if ext in [".pth", ".pt"]:
            #     buffer = io.BytesIO(decompressed_data)
            #     checkpoint = torch.load(buffer, map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            #     if "model_state_dict" in checkpoint and "config" in checkpoint:
            #         self.model_config = checkpoint["config"]
            #         if self.model_config.get("model_type") == "HybridModel":
            #             if not verify_config_integrity(self.model_config):
            #                 raise ValueError("Config integrity check failed.")
            #             client_model = create_hybrid_model(self.model_config)
            #             client_model.load_state_dict(checkpoint["model_state_dict"], strict=False)
            #         else:
            #             client_model = create_model_from_state_dict(checkpoint["model_state_dict"])
            #             client_model.load_state_dict(checkpoint["model_state_dict"], strict=False)
            #         if "optimizer_state_dict" in checkpoint:
            #             self.optimizer_state = checkpoint["optimizer_state_dict"]
            #             if isinstance(self.optimizer_state, tuple):
            #                 self.optimizer_state = self.optimizer_state[0]
            #     elif isinstance(checkpoint, dict):
            #         client_model = create_model_from_state_dict(checkpoint)
            #         client_model.load_state_dict(checkpoint, strict=False)
            #     else:
            #         client_model = checkpoint
            # elif ext == ".pkl":
            #     client_model = pickle.loads(decompressed_data)
            # elif ext == ".h5":
            #     with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            #         tmp.write(decompressed_data)
            #         tmp.flush()
            #         client_model = tf_load_model(tmp.name)
            #         os.unlink(tmp.name)
            # else:
            #     error_msg = f"ERROR: Unsupported model format: {ext}\n"
            #     writer.write(error_msg.encode("utf-8", errors="replace"))
            #     await writer.drain()
            #     server_logger.error(f"Unsupported model format from client {client_ip}: {ext}")
            #     return
            # CHANGED: Initialize model from client update, mimicking initialize_model
            # WHERE: After saving the temporary file
            try:
                client_model = None
                client_optimizer_state = None
                client_model_config = self.pre_update_config.copy() if self.pre_update_config else {}
                if ext in [".pth", ".pt"]:
                    buffer = io.BytesIO(decompressed_data)
                    checkpoint = torch.load(buffer, map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
                    if isinstance(checkpoint, dict):
                        if "model_state_dict" in checkpoint and "config" in checkpoint:
                            client_model_config = checkpoint["config"]
                            if self.pre_update_config and client_model_config != self.pre_update_config:
                                raise ValueError("Client model config does not match the current global model config")
                            if client_model_config.get("model_type") == "HybridModel":
                                if not verify_config_integrity(client_model_config):
                                    raise ValueError("Config integrity check failed.")
                                client_model = create_hybrid_model(client_model_config)
                            else:
                                client_model = create_model_from_state_dict(checkpoint["model_state_dict"])
                            client_model.load_state_dict(checkpoint["model_state_dict"], strict=False)
                            if "optimizer_state_dict" in checkpoint:
                                client_optimizer_state = checkpoint["optimizer_state_dict"]
                                if isinstance(client_optimizer_state, tuple):
                                    client_optimizer_state = client_optimizer_state[0]
                        else:
                            client_model = create_model_from_state_dict(checkpoint)
                            client_model.load_state_dict(checkpoint, strict=False)
                        # elif "model_state_dict" in checkpoint:
                        #     self.model = create_model_from_state_dict(checkpoint["model_state_dict"])
                        #     self.model.load_state_dict(checkpoint["model_state_dict"], strict=False)
                        #     self.optimizer_state = None
                        # else:
                        #     self.model = create_model_from_state_dict(checkpoint)
                        #     self.model.load_state_dict(checkpoint, strict=False)
                        #     self.optimizer_state = None
                    else:
                        client_model = checkpoint
                elif ext == ".pkl":
                    client_model = pickle.loads(decompressed_data)
                elif ext == ".h5":
                    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
                        tmp.write(decompressed_data)
                        tmp.flush()
                        client_model = tf_load_model(tmp.name)
                        os.unlink(tmp.name)
                else:
                    raise ValueError(f"Unsupported model format: {ext}")

                # Validate the initialized model
                # WHERE: After initialization attempt
                test_dataset = CustomDataset(test_dataset_path)
                original_model = self.model
                self.model = client_model
                metrics = self.evaluate_model(test_dataset)
                self.model = original_model
                if metrics is None or metrics["accuracy"] < 0.1:  # Arbitrary threshold for validity
                    raise ValueError("Model update resulted in invalid or extremely poor performance")

                server_logger.info(f"Successfully initialized model from client update {client_model_path}")

            except Exception as e:
                server_logger.error(f"Failed to initialize model from client update: {e}. Reverting to pre-update state.")
                if self.pre_update_state is not None and self.pre_update_config is not None:
                    # Revert architecture and parameters
                    if self.pre_update_config.get("model_type") == "HybridModel":
                        self.model = create_hybrid_model(self.pre_update_config)
                    else:
                        self.model = create_model_from_state_dict(self.pre_update_state)
                    self.model.load_state_dict(self.pre_update_state)
                    self.model_config = self.pre_update_config
                    self.optimizer_state = self.pre_update_optimizer_state
                    server_logger.info("Reverted to pre-update state (parameters, config, optimizer)")
                else:
                    server_logger.warning("No complete pre-update state available to revert to.")
                error_msg = f"ERROR: Failed to process update - {e}\n"
                writer.write(error_msg.encode("utf-8"))
                await writer.drain()
                return

            client_model_filename = f"client_model_{client_ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            client_model_path = os.path.join(client_models_dir, client_model_filename)
            if ext in [".pth", ".pt"]:
                if isinstance(client_model, nn.Module):
                    with open(client_model_path, "wb") as f:
                        checkpoint_to_save = {"model_state_dict": client_model.state_dict(), "optimizer_state_dict": client_optimizer_state, "config": client_model_config}
                        torch.save(checkpoint_to_save, f)
                else:
                    with open(client_model_path, "wb") as f:
                        torch.save(client_model, f)
            elif ext == ".h5":
                client_model.save(client_model_path)
            else:
                with open(client_model_path, "wb") as f:
                    pickle.dump(client_model, f)
            server_logger.info(f"Client model saved at {client_model_path}")

            # async with model_lock:
            #     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            #     if isinstance(self.model, nn.Module):
            #         self.model.to(device)
            #     self.update_queue.append((self.model, client_ip))
            #     logger.debug(f"Client update from {client_ip} added to queue. Queue size: {len(self.update_queue)}")
            # writer.write(b"UPDATE_RECEIVED\n")
            # await writer.drain()
            # logger.info(f"Client update received from {client_ip}")
            # await self.aggregate_and_evaluate()
            # Add model, client IP, and optimizer state to update queue
            async with model_lock:
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                if isinstance(client_model, nn.Module):
                    client_model.to(device)
                self.update_queue.append((client_model, client_ip, client_optimizer_state))
                server_logger.debug(f"Client update from {client_ip} added to queue with optimizer state. Queue size: {len(self.update_queue)}")
            writer.write(b"UPDATE_RECEIVED\n")
            await writer.drain()
            server_logger.info(f"Client update received from {client_ip}")
            await self.aggregate_and_evaluate()

        except asyncio.TimeoutError:
            server_logger.warning(f"Timeout during update from {client_ip} - possible stealth scan or network issue")
        except ConnectionResetError:
            server_logger.warning(f"Connection reset during update from {client_ip} - possible stealth scan or client drop")

        except Exception as e:
            error_msg = f"ERROR: {e}\n"
            writer.write(error_msg.encode("utf-8"))
            await writer.drain()
            server_logger.error(f"Failed to receive update from client {client_ip}: {e}")
            master_error(f"Failed to receive update from client {client_ip}: {e}")
        finally:
            addr = writer.get_extra_info('peername')
            server_logger.debug(f"Finished update receive for {addr}")
            master_info(f"Finished update receive for {addr}")
    async def send_model(self, writer):
        try:
            ext = os.path.splitext(global_model_file)[1]
            server_logger.info(f"Preparing to send global model with type {ext}")
            if ext in [".pth", ".pt"]:
                buffer = io.BytesIO()
                checkpoint = {"model_state_dict": self.model.state_dict(), "optimizer_state_dict": self.optimizer_state, "config": self.model_config}
                torch.save(checkpoint, buffer)
                buffer.seek(0)
                serialized_model = buffer.read()
            elif ext == ".pkl":
                serialized_model = pickle.dumps(self.model)
            else:
                serialized_model = pickle.dumps(self.model)
            compressed_model = zlib.compress(serialized_model)
            header = f"TYPE:{ext}|SIZE:{len(compressed_model)}\n".encode("utf-8", errors="replace")
            server_logger.debug(f"Sending {len(compressed_model)} bytes to client")
            writer.write(header)
            await writer.drain()
            writer.write(compressed_model)
            await writer.drain()
            server_logger.info("Global model sent to client with header.")
            master_info("Global model sent to client with header.")
        except Exception as e:
            error_msg = f"ERROR: {e}\n"
            writer.write(error_msg.encode("utf-8", errors="replace"))
            await writer.drain()
            server_logger.error(f"Failed to send model: {e}")
            master_error(f"Failed to send model: {e}")

    def evaluate_model(self, test_dataset):
        import traceback
        server_logger.info("Starting model evaluation on test dataset.")
        y_true = []
        y_pred = []
        try:
            if isinstance(self.model, nn.Module):
                test_loader = DataLoader(
                    test_dataset,
                    batch_size=16,
                    shuffle=False,
                    num_workers=0,
                    pin_memory=torch.cuda.is_available()
                )
                self.model.eval()
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                self.model.to(device)
                batch_counter = 0
                with torch.no_grad():
                    for inputs, labels in test_loader:
                        batch_counter += 1
                        inputs, labels = inputs.to(device), labels.to(device)
                        outputs = self.model(inputs)
                        _, predicted = torch.max(outputs, 1)
                        y_true.extend(labels.cpu().numpy())
                        y_pred.extend(predicted.cpu().numpy())
                        if batch_counter % 10 == 0:
                            torch.cuda.empty_cache()
                server_logger.info(f"Completed evaluation of {batch_counter} batches.")
            elif hasattr(self.model, "predict"):
                if not (hasattr(test_dataset, 'features') and hasattr(test_dataset, 'labels')):
                    raise ValueError("Test dataset must have 'features' and 'labels' attributes.")
                x_test = test_dataset.features.reset_index(drop=True).to_numpy()
                y_test = test_dataset.labels.reset_index(drop=True).to_numpy()
                server_logger.info(f"Using TensorFlow/Keras model for evaluation. x_test shape: {x_test.shape}, y_test shape: {y_test.shape}")
                y_pred = self.model.predict(x_test)
                y_true = y_test
            else:
                raise ValueError(f"Unsupported model type: {type(self.model)}")
        except Exception as e:
            server_logger.error(f"Error during model evaluation: {e}")
            master_error(f"Error during model evaluation: {e}")
            traceback.print_exc()
            track_ = traceback.format_exc()
            server_logger.debug(track_)
            return None
        try:
            metrics = compute_all_metrics(np.array(y_true), np.array(y_pred))
            server_logger.info(f"Evaluation metrics computed: {metrics}")

            return metrics
        except Exception as e:
            server_logger.error(f"Error during metric computation: {e}")
            master_error(f"Error during metric computation: {e}")
            return None

    async def aggregate_and_evaluate(self):
        server_logger.debug("Acquiring model lock")
        async with model_lock:
            if len(self.update_queue) == 0:
                server_logger.info("No updates in queue to aggregate.")
                return
            
            if(self.optimizer_state is None):
                server_logger.error(f"Optimizer state is None. Cannot aggregate and evaluate. {self.optimizer_state}")
            
            if (self.pre_update_optimizer_state is None):
                server_logger.error(f"Pre update optimizer state is None. Cannot aggregate and evaluate. {self.pre_update_optimizer_state}")

            server_logger.info(f"Aggregating {len(self.update_queue)} client updates.")
            client_models = [entry[0] for entry in self.update_queue]
            client_ips = [entry[1] for entry in self.update_queue]
            client_optimizer_states = [entry[2] for entry in self.update_queue]

            if any(state is None for state in client_optimizer_states):
                    server_logger.error(f"Optimizer state is None client optimizer state. {client_optimizer_states}")
                    master_error(f"Optimizer state is None client optimizer state. {client_optimizer_states}")

            test_dataset = CustomDataset(test_dataset_path)
            weights = []
            similarities = []
            validation_records = []
            for idx, cm in enumerate(client_models):
                self.model = cm  # Temporarily assign for evaluation
                metrics = self.evaluate_model(test_dataset)
                weight = metrics["accuracy"] if metrics else 0
                weights.append(weight)
                similarity = cosine_similarity_from_states(self.pre_update_state, cm.state_dict()) if self.pre_update_state is not None and hasattr(cm, "state_dict") else None
                similarities.append(similarity)
                reason = ""
                if metrics is None or weight <= 0:
                    reason = "server_validation_failed"
                elif similarity is None or not math.isfinite(similarity):
                    reason = "invalid_cosine_similarity"
                validation_records.append({
                    "client_ip": client_ips[idx],
                    "metrics": metrics,
                    "cosine_similarity": similarity,
                    "reason": reason,
                })
                if metrics:
                    server_logger.info(f"Client model accuracy: {metrics['accuracy']:.4f}, cosine similarity: {similarity}")
                else:
                    server_logger.warning(f"Client model evaluation failed; cosine similarity: {similarity}")

            valid_indices = [
                idx for idx, (weight, similarity) in enumerate(zip(weights, similarities))
                if weight > 0 and similarity is not None and math.isfinite(similarity)
            ]
            finite_similarities = [similarities[idx] for idx in valid_indices]
            if len(finite_similarities) > 1:
                mean_similarity = float(np.mean(finite_similarities))
                std_similarity = float(np.std(finite_similarities))
                if std_similarity > 0:
                    before_cosine_filter = set(valid_indices)
                    valid_indices = [
                        idx for idx in valid_indices
                        if abs(similarities[idx] - mean_similarity) <= COSINE_ANOMALY_LAMBDA * std_similarity
                    ]
                    for rejected_idx in before_cosine_filter - set(valid_indices):
                        validation_records[rejected_idx]["reason"] = "cosine_similarity_outlier"

            if not valid_indices:
                server_logger.warning("All client updates failed validation/cosine filtering; reverting to pre-update state.")
                log_update_validation_records(validation_records, valid_indices)
                if self.pre_update_state is not None and self.pre_update_config is not None:
                    if self.pre_update_config.get("model_type") == "HybridModel":
                        self.model = create_hybrid_model(self.pre_update_config)
                    else:
                        self.model = create_model_from_state_dict(self.pre_update_state)
                    self.model.load_state_dict(self.pre_update_state)
                    self.model_config = self.pre_update_config
                    self.optimizer_state = self.pre_update_optimizer_state
                self.update_queue.clear()
                return

            rejected_ips = [client_ips[idx] for idx in range(len(client_ips)) if idx not in valid_indices]
            if rejected_ips:
                server_logger.warning(f"Rejected anomalous or invalid client updates before aggregation: {rejected_ips}")
            log_update_validation_records(validation_records, valid_indices)
            client_models = [client_models[idx] for idx in valid_indices]
            client_ips = [client_ips[idx] for idx in valid_indices]
            client_optimizer_states = [client_optimizer_states[idx] for idx in valid_indices]
            weights = [weights[idx] for idx in valid_indices]
            self.model = None  # Reset after evaluation

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            server_logger.debug(f"Aggregation will use device: {device}")

            try:
                previous_weight = self.previous_accuracy if self.previous_accuracy is not None else 1.0
                total_weight = sum(weights) + previous_weight

                # Aggregate model state
                aggregated_state = {}
                # Initialize aggregated_state with zeros on the correct device
                for name, param in client_models[0].state_dict().items():
                    aggregated_state[name] = torch.zeros_like(param, device=device)

                # Add previous model state from pre_update_state (ensure it's on the correct device)
                if self.pre_update_state is not None:
                    for name, param in self.pre_update_state.items():
                        aggregated_state[name] += param.to(device) * (previous_weight / total_weight)
                else:
                    server_logger.warning("No pre_update_state available; skipping previous state contribution.")

                # Add client model states (ensure they're on the correct device)
                for cm, weight in zip(client_models, weights):
                    cm.to(device)  # Move the entire model to the device
                    for name, param in cm.state_dict().items():
                        aggregated_state[name] += param.to(device) * (weight / total_weight)

                # # Aggregate optimizer state (if available)
                # aggregated_optimizer_state = None  # Initialize outside the if block
                # if all(state is not None for state in client_optimizer_states) and self.pre_update_optimizer_state is not None:
                #     aggregated_optimizer_state = {}
                #     first_opt_state = client_optimizer_states[0]
                #     # Copy param_groups structure
                #     for group_idx, group in enumerate(first_opt_state['param_groups']):
                #         aggregated_optimizer_state.setdefault('param_groups', []).append({})
                #         for key in group:
                #             if key != 'params':
                #                 aggregated_optimizer_state['param_groups'][group_idx][key] = group[key]

                #     # Initialize state tensors on the correct device
                #     aggregated_optimizer_state['state'] = {}
                #     for param_id, state in first_opt_state['state'].items():
                #         aggregated_optimizer_state['state'][param_id] = {}
                #         for key in state:
                #             if torch.is_tensor(state[key]):
                #                 aggregated_optimizer_state['state'][param_id][key] = torch.zeros_like(state[key], device=device)

                #     # Add previous optimizer state (ensure it's on the correct device)
                #     for param_id, state in self.pre_update_optimizer_state['state'].items():
                #         for key in state:
                #             if torch.is_tensor(state[key]):
                #                 aggregated_optimizer_state['state'][param_id][key] += state[key].to(device) * (previous_weight / total_weight)

                #     # Add client optimizer states (ensure they're on the correct device)
                #     for opt_state, weight in zip(client_optimizer_states, weights):
                #         for param_id, state in opt_state['state'].items():
                #             for key in state:
                #                 if torch.is_tensor(state[key]):
                #                     aggregated_optimizer_state['state'][param_id][key] += state[key].to(device) * (weight / total_weight)

                # CHANGED: Create and load the model before optimizer state aggregation
            # Load aggregated states into the global model first
                if self.model_config.get("model_type") == "HybridModel":
                    self.model = create_hybrid_model(self.model_config)
                else:
                    self.model = create_model_from_state_dict(aggregated_state)
                self.model.load_state_dict(aggregated_state)
                self.model.to(device)



                # Aggregate optimizer state
                aggregated_optimizer_state = None
                if self.pre_update_optimizer_state is not None or any(state is not None for state in client_optimizer_states):
                    # CHANGED: Start with a fresh optimizer state to ensure valid structure
                    optimizer = optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=0.01)
                    aggregated_optimizer_state = optimizer.state_dict()  # Start with a valid base state

                    # CHANGED: Aggregate only the 'state' portion, mapping to current model parameters
                    valid_states = [state for state in [self.pre_update_optimizer_state] + client_optimizer_states if state is not None]
                    if valid_states:
                        # Ensure parameter IDs match the current model
                        param_to_id = {id(p): i for i, p in enumerate(self.model.parameters())}
                        for opt_state in valid_states:
                            weight = previous_weight if opt_state is self.pre_update_optimizer_state else weights[client_optimizer_states.index(opt_state)]
                            for param_id, state in opt_state['state'].items():
                                if param_id in param_to_id:  # Only aggregate if param ID matches current model
                                    agg_param_id = param_to_id[param_id]
                                    if agg_param_id not in aggregated_optimizer_state['state']:
                                        aggregated_optimizer_state['state'][agg_param_id] = {}
                                    for key in state:
                                        if torch.is_tensor(state[key]):
                                            if key not in aggregated_optimizer_state['state'][agg_param_id]:
                                                aggregated_optimizer_state['state'][agg_param_id][key] = torch.zeros_like(state[key], device=device)
                                            aggregated_optimizer_state['state'][agg_param_id][key] += state[key].to(device) * (weight / total_weight)

                        # CHANGED: Retain 'param_groups' from fresh optimizer, including 'params'
                        aggregated_optimizer_state['param_groups'] = optimizer.state_dict()['param_groups']
                

                # Load aggregated states into the global model
                if self.model_config.get("model_type") == "HybridModel":
                    self.model = create_hybrid_model(self.model_config)
                else:
                    self.model = create_model_from_state_dict(aggregated_state)

                
                self.model.load_state_dict(aggregated_state)
                self.model.to(device)

                if(self.optimizer_state is None):
                    server_logger.error(f"Optimizer state is None before loading aggregation. {self.optimizer_state}")

                # CHANGED: Added try-except to handle optimizer state loading errors
                optimizer = optim.AdamW(self.model.parameters(), lr=1e-5, weight_decay=0.01)
                if aggregated_optimizer_state is not None:
                    try:
                        optimizer.load_state_dict(aggregated_optimizer_state)
                        server_logger.info("Aggregated optimizer state loaded successfully.")
                    except Exception as e:
                        server_logger.warning(f"Failed to load aggregated optimizer state: {e}. Using default optimizer state.")
                else:
                    server_logger.info("No optimizer states aggregated. Initializing default.")
                self.optimizer_state = optimizer.state_dict()
                # END CHANGE

                server_logger.info("Aggregation completed with previous model state included.")
            except Exception as e:
                server_logger.error(f"Error aggregating model/optimizer state: {str(e)}", exc_info=True)  # Log full stack trace # Ensure model and config are restored if aggregation fails
                if self.pre_update_state is not None and self.pre_update_config is not None:
                    try:
                        if self.pre_update_config.get("model_type") == "HybridModel":
                            self.model = create_hybrid_model(self.pre_update_config)
                        else:
                            self.model = create_model_from_state_dict(self.pre_update_state)
                        self.model.load_state_dict(self.pre_update_state)
                        self.model_config = self.pre_update_config
                        self.optimizer_state = self.pre_update_optimizer_state
                        server_logger.info("Restored pre-update state due to aggregation failure.")
                    except Exception as restore_e:
                        server_logger.error(f"Failed to restore pre-update state after aggregation error: {restore_e}")
                else:
                    server_logger.warning("No pre-update state available to restore after aggregation failure.")
                if(self.optimizer_state is None):
                    server_logger.error(f"Optimizer state is None. {self.optimizer_state}")
                return

                
            self.update_queue.clear()

        server_logger.debug("Releasing model lock")
        self.clean_connection_attempts()  # Clean up connection attempts after aggregation
        # Fine-tune on test_dataset to match client's evaluation
        # self.fine_tune_model(test_dataset_path, epochs=10, lr=1e-5, test_dataset=test_dataset)
        if(self.optimizer_state is None):
            server_logger.error(f"Optimizer state is None after aggregation before evaluation. {self.optimizer_state}")
        metrics = self.evaluate_model(test_dataset)
        if metrics is None:
            server_logger.error("Evaluation failed; skipping performance logging.")
            return
        
        new_accuracy = metrics["accuracy"] * 100
        previous_accuracy = (self.previous_accuracy * 100) if self.previous_accuracy is not None else new_accuracy

        accuracy_drop_exceeded = (
            self.previous_accuracy is not None
            and metrics["accuracy"] < (self.previous_accuracy - ROLLBACK_ACCURACY_DROP)
        )
        if accuracy_drop_exceeded:
            if self.pre_update_state is not None and self.pre_update_config is not None:
                try:
                    if self.pre_update_config.get("model_type") == "HybridModel":
                        self.model = create_hybrid_model(self.pre_update_config)
                    else:
                        self.model = create_model_from_state_dict(self.pre_update_state)
                    self.model.load_state_dict(self.pre_update_state)
                    self.model_config = self.pre_update_config
                    self.optimizer_state = self.pre_update_optimizer_state
                    server_logger.info(f"Aggregated update rejected: new accuracy {new_accuracy:.2f}% dropped more than {ROLLBACK_ACCURACY_DROP * 100:.1f}% from previous {previous_accuracy:.2f}%. Reverted to full pre-update state.")
                except Exception as e:
                    server_logger.error(f"Failed to revert to pre-update state: {e}")
                    master_error(f"Failed to revert to pre-update state: {e}")
            else:
                server_logger.warning("No complete pre-update state available to revert to.")
                master_error("No complete pre-update state available to revert to.")
        else:
            self.previous_accuracy = new_accuracy / 100
            self.model_version += 1
            if(self.optimizer_state is None):
                server_logger.error(f"Optimiser state is None. {self.optimizer_state}")
            self.save_model()
            server_logger.info(f"Aggregated update accepted: new accuracy {new_accuracy:.2f}% vs previous {previous_accuracy:.2f}%.")
            log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            name_field = ", ".join(set(client_ips))
            performance_row = [
                name_field,
                f"{metrics['accuracy']:.4f}",
                f"{metrics['precision']:.4f}",
                f"{metrics['recall']:.4f}",
                f"{metrics['f1_score']:.4f}",
                f"{metrics['mcc']:.4f}",
                f"{metrics['markedness']:.4f}",
                f"{metrics['youdens_j']:.4f}",
                f"{metrics['fmi']:.4f}",
                log_time
            ]
            with open(model_performance_log, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(performance_row)
            server_logger.info(f"Performance metrics logged: {performance_row}")

    async def start_server(self):
        server_logger.info("Starting server...")
        server_logger.info(f"Attempting to start server on {self.host}:{self.port}")

        try:
            self.blacklist = await self.load_blacklist()
            await self.clean_expired_blacklist_entries()  # Clean expired entries on startup
        except Exception as e:
            server_logger.error(f"Failed to load blacklist during startup: {e}. Starting with empty blacklist.")
            master_error(f"Failed to load blacklist during startup: {e}. Starting with empty blacklist.")
            self.blacklist = {}


        test_dataset = CustomDataset(test_dataset_path)
        server_logger.info(f"Initial dataset size: {len(test_dataset)}")
        metrics = self.evaluate_model(test_dataset)
        if metrics is not None:
            self.previous_accuracy = metrics["accuracy"]
            server_logger.info(f"Initial global model accuracy: {metrics['accuracy']}")
        # CHANGED: Enhanced TLS setup with detailed logging from server26.py
        ssl_context = True
        if USE_TLS:
            server_logger.info(f"Configuring TLS with cert file: {TLS_CERT_FILE} and key file: {TLS_KEY_FILE}")
            try:
                cert_result = ensure_tls_certificates(project_root=os.path.dirname(os.path.abspath(__file__)), server_host=self.host)
                server_logger.info(f"TLS certificates ready: {cert_result}")
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(certfile=TLS_CERT_FILE, keyfile=TLS_KEY_FILE)
                server_logger.info("TLS context successfully configured")
            except FileNotFoundError as e:
                server_logger.error(f"TLS configuration failed: Certificate or key file not found - {e}")
                master_error(f"TLS configuration failed: Certificate or key file not found - {e}")
                raise
            except Exception as e:
                server_logger.error(f"TLS configuration failed: {e}")
                master_error(f"TLS configuration failed: {e}")
                raise

        server = await asyncio.start_server(self.log_connection_attempt, self.host, self.port, ssl=ssl_context)
        addr = server.sockets[0].getsockname()
        server_logger.info(f"Server successfully bound and running on {addr}")
        server_logger.debug(f"Server socket details: {server.sockets[0].getsockname()}")

        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    server = FederatedLearningServer()
    try:
        asyncio.run(server.start_server())
        
    except KeyboardInterrupt:
        server_logger.info("Server shutting down.")
        asyncio.run(server.save_blacklist())
    except Exception as e:
        server_logger.error(f"Server crashed unexpectedly: {e}")
        asyncio.run(server.save_blacklist())
