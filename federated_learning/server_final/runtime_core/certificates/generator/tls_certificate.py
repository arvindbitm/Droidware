#!/usr/bin/env python3
import datetime
import json
import os
import shutil
from ipaddress import ip_address
from pathlib import Path

import cryptography.x509 as x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


DEFAULT_HOSTNAMES = {"localhost", "federated-server.droidware"}
DEFAULT_IPS = {"127.0.0.1"}


def _project_root():
    return Path(__file__).resolve().parents[1]


def _read_server_host(project_root):
    return os.getenv("DROIDWARE_SERVER_HOST", "127.0.0.1")


def _split_san_host(host):
    try:
        return None, str(ip_address(host))
    except ValueError:
        return host, None


def _expected_sans(server_host):
    dns_names = set(DEFAULT_HOSTNAMES)
    ip_names = set(DEFAULT_IPS)
    dns_name, ip_name = _split_san_host(server_host)
    if dns_name:
        dns_names.add(dns_name)
    if ip_name:
        ip_names.add(ip_name)
    return dns_names, ip_names


def _cert_matches(cert_file, server_host):
    if not cert_file.exists():
        return False
    try:
        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns_names = set(san.get_values_for_type(x509.DNSName))
        ip_names = {str(value) for value in san.get_values_for_type(x509.IPAddress)}
        expected_dns, expected_ips = _expected_sans(server_host)
        return expected_dns.issubset(dns_names) and expected_ips.issubset(ip_names)
    except Exception:
        return False


def generate_tls_cert(cert_file, key_file, server_host="127.0.0.1", days_valid=365):
    cert_file = Path(cert_file)
    key_file = Path(key_file)
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Mathura"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "GLA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DROIDWARE"),
        x509.NameAttribute(NameOID.COMMON_NAME, server_host),
    ])

    expected_dns, expected_ips = _expected_sans(server_host)
    san_entries = [x509.DNSName(name) for name in sorted(expected_dns)]
    san_entries.extend(x509.IPAddress(ip_address(value)) for value in sorted(expected_ips))

    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_file.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def ensure_tls_certificates(project_root=None, server_host=None, force=False):
    project_root = Path(project_root) if project_root else _project_root()
    server_host = server_host or _read_server_host(project_root)

    server_cert = project_root / "cert.pem"
    server_key = project_root / "key.pem"
    cert_needs_update = force or not server_key.exists() or not _cert_matches(server_cert, server_host)

    if cert_needs_update:
        generate_tls_cert(server_cert, server_key, server_host=server_host)

    for relative_dir in ("admin", "client"):
        target_dir = project_root / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(server_cert, target_dir / "cert.pem")

    tls_host_dir = project_root / "tls_certificate" / server_host
    tls_host_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(server_cert, tls_host_dir / "cert.pem")
    shutil.copy2(server_key, tls_host_dir / "key.pem")

    return {
        "server_cert": str(server_cert),
        "server_key": str(server_key),
        "admin_cert": str(project_root / "admin" / "cert.pem"),
        "client_cert": str(project_root / "client" / "cert.pem"),
        "host_archive": str(tls_host_dir),
        "generated": cert_needs_update,
    }


if __name__ == "__main__":
    force = "--force" in os.sys.argv
    result = ensure_tls_certificates(force=force)
    status = "generated" if result["generated"] else "already valid"
    print(f"TLS certificate is {status}.")
    for key, value in result.items():
        if key != "generated":
            print(f"{key}: {value}")
