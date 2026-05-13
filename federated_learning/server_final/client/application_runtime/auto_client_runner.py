#!/usr/bin/env python3
import argparse
import asyncio
import builtins
import os
import re
import time
from pathlib import Path

import client12


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
MFA_LOG = PROJECT_DIR / "logs" / "mfa.log"


def wait_for_otp(log_path, start_size=0, timeout=180):
    deadline = time.time() + timeout
    pattern = re.compile(r"Generated OTP:\s*(\d{6})")

    while time.time() < deadline:
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(start_size)
                text = handle.read()
            matches = pattern.findall(text)
            if matches:
                return matches[-1]
        time.sleep(1)

    raise TimeoutError(f"Timed out waiting for OTP in {log_path}")


def run(server_address, username, password, rounds, train_data=None, test_data=None):
    if train_data:
        os.environ["DROIDWARE_TRAIN_DATA"] = train_data
    if test_data:
        os.environ["DROIDWARE_TEST_DATA"] = test_data

    start_size = MFA_LOG.stat().st_size if MFA_LOG.exists() else 0
    original_input = builtins.input

    def otp_input(prompt=""):
        if "Enter OTP" in prompt:
            otp = wait_for_otp(MFA_LOG, start_size=start_size)
            print(f"{prompt}{otp}")
            return otp
        return original_input(prompt)

    builtins.input = otp_input
    try:
        token, _, hmac_key = asyncio.run(
            client12.authenticate(server_address, username, password)
        )
    finally:
        builtins.input = original_input

    if not token or not hmac_key:
        raise RuntimeError("Authentication failed; token or HMAC key missing.")

    for round_index in range(rounds):
        print(f"Starting client round {round_index + 1}/{rounds}")
        client12.main(server_address, token=token, hmac_key=hmac_key)

    print("Client validation run finished.")


def parse_args():
    parser = argparse.ArgumentParser(description="Run Droidware client with OTP auto-read from local MFA log.")
    parser.add_argument("--server", default="127.0.0.1:6000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--train-data")
    parser.add_argument("--test-data")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        server_address=args.server,
        username=args.username,
        password=args.password,
        rounds=args.rounds,
        train_data=args.train_data,
        test_data=args.test_data,
    )
