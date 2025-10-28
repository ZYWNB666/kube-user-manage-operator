"""
Generate a kubeconfig for a ServiceAccount without pre-running shell scripts.

Examples:
    python create-kubeconfig.py my-service-account \
        --namespace kube-system \
        --cluster-name my-cluster \
        --api-server https://10.0.0.1:6443
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output-kubeconfig"


class CommandError(RuntimeError):
    """Raised when a subprocess command fails."""


def run(cmd: list, *, input_data: Optional[str] = None) -> str:
    """Run a command and return stdout or raise CommandError on failure."""
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "no output"
        raise CommandError(f"Command {' '.join(cmd)} failed: {details}")
    return result.stdout


def extract_cluster_metadata(
    data: Dict,
    *,
    source_path: Optional[Path],
    context: Optional[str],
    cluster_name: Optional[str],
    api_server: Optional[str],
) -> Tuple[str, str, str, bool]:
    """Extract cluster_name, api_server, ca_data, insecure flag from config dict."""
    current_context = context or data.get("current-context")
    if not current_context:
        raise ValueError("Unable to determine context; specify --context.")

    contexts = {item["name"]: item["context"] for item in data.get("contexts", [])}
    if current_context not in contexts:
        raise ValueError(f"Context '{current_context}' not found in kubeconfig.")

    context_obj = contexts[current_context]
    resolved_cluster_name = cluster_name or context_obj.get("cluster")
    if not resolved_cluster_name:
        raise ValueError("Cluster name could not be resolved; specify --cluster-name.")

    clusters = {item["name"]: item["cluster"] for item in data.get("clusters", [])}
    if resolved_cluster_name not in clusters:
        raise ValueError(f"Cluster '{resolved_cluster_name}' not present in kubeconfig.")

    cluster_obj = clusters[resolved_cluster_name]
    resolved_api_server = api_server or cluster_obj.get("server")
    if not resolved_api_server:
        raise ValueError("API server URL could not be resolved; specify --api-server.")

    ca_data = cluster_obj.get("certificate-authority-data")
    ca_path = cluster_obj.get("certificate-authority")
    insecure = bool(cluster_obj.get("insecure-skip-tls-verify", False))

    if not ca_data and not insecure:
        if not ca_path:
            raise ValueError(
                "Neither certificate-authority-data nor certificate-authority path "
                "found in kubeconfig; provide --kubeconfig with embedded CA data."
            )
        ca_file = Path(ca_path)
        if not ca_file.is_absolute():
            if source_path is None:
                raise ValueError(
                    "Relative certificate-authority path requires --kubeconfig file."
                )
            ca_file = (source_path.parent / ca_file).resolve()
        ca_bytes = ca_file.read_bytes()
        ca_data = base64.b64encode(ca_bytes).decode("utf-8")

    return resolved_cluster_name, resolved_api_server, ca_data or "", insecure


def load_kubeconfig_from_file(
    path: Path,
    context: Optional[str],
    cluster_name: Optional[str],
    api_server: Optional[str],
) -> Tuple[str, str, str, bool]:
    """Read cluster metadata from a kubeconfig file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return extract_cluster_metadata(
        data,
        source_path=path,
        context=context,
        cluster_name=cluster_name,
        api_server=api_server,
    )


def load_kubeconfig_from_kubectl(
    context: Optional[str],
    cluster_name: Optional[str],
    api_server: Optional[str],
) -> Tuple[str, str, str, bool]:
    """Read cluster metadata via `kubectl config view`."""
    output = run(["kubectl", "config", "view", "--raw", "-o", "json"])
    data = json.loads(output)
    return extract_cluster_metadata(
        data,
        source_path=None,
        context=context,
        cluster_name=cluster_name,
        api_server=api_server,
    )


def find_or_create_token_secret(
    sa_name: str,
    namespace: str,
    secret_name: Optional[str],
    wait_seconds: int = 30,
) -> Tuple[str, Dict]:
    """
    Ensure a service-account token Secret exists.

    Returns the secret name and its JSON manifest.
    """
    if secret_name:
        secret_data = json.loads(
            run(["kubectl", "get", "secret", secret_name, "-n", namespace, "-o", "json"])
        )
        return secret_name, secret_data

    sa_data = json.loads(
        run(["kubectl", "get", "sa", sa_name, "-n", namespace, "-o", "json"])
    )

    for ref in sa_data.get("secrets") or []:
        name = ref.get("name")
        if not name:
            continue
        try:
            secret_data = json.loads(
                run(["kubectl", "get", "secret", name, "-n", namespace, "-o", "json"])
            )
        except CommandError:
            continue
        if secret_data.get("type") != "kubernetes.io/service-account-token":
            continue
        annotations = secret_data.get("metadata", {}).get("annotations", {})
        if annotations.get("kubernetes.io/service-account.name") != sa_name:
            continue
        token_present = bool(secret_data.get("data", {}).get("token"))
        if token_present:
            return name, secret_data

    secret_name = f"{sa_name}-token"
    manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
            "annotations": {"kubernetes.io/service-account.name": sa_name},
        },
        "type": "kubernetes.io/service-account-token",
    }

    run(
        ["kubectl", "apply", "-f", "-"],
        input_data=yaml.safe_dump(manifest, sort_keys=False),
    )

    if sa_data.get("secrets"):
        patch = json.dumps(
            [{"op": "add", "path": "/secrets/-", "value": {"name": secret_name}}]
        )
    else:
        patch = json.dumps(
            [{"op": "add", "path": "/secrets", "value": [{"name": secret_name}]}]
        )

    run(
        [
            "kubectl",
            "patch",
            "sa",
            sa_name,
            "-n",
            namespace,
            "--type=json",
            "-p",
            patch,
        ]
    )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        secret_data = json.loads(
            run(["kubectl", "get", "secret", secret_name, "-n", namespace, "-o", "json"])
        )
        token = secret_data.get("data", {}).get("token")
        if token:
            return secret_name, secret_data
        time.sleep(1)

    raise RuntimeError(
        f"Timed out waiting for token in secret '{secret_name}' within {wait_seconds}s."
    )


def build_kubeconfig(
    sa_name: str,
    namespace: str,
    cluster_name: str,
    api_server: str,
    ca_data: str,
    token: str,
    insecure_skip_tls: bool,
) -> Dict:
    """Assemble the kubeconfig document."""
    context_name = f"{sa_name}@{cluster_name}"
    cluster_block = {
        "server": api_server,
        "insecure-skip-tls-verify": bool(insecure_skip_tls),
    }
    if not insecure_skip_tls:
        cluster_block["certificate-authority-data"] = ca_data

    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": cluster_name, "cluster": cluster_block}],
        "contexts": [
            {
                "name": context_name,
                "context": {
                    "cluster": cluster_name,
                    "user": sa_name,
                    "namespace": namespace,
                },
            }
        ],
        "current-context": context_name,
        "users": [{"name": sa_name, "user": {"token": token}}],
    }


def preferred_kubeconfig_path() -> Optional[Path]:
    """Select a reasonable kubeconfig file if available."""
    env_path = os.environ.get("KUBECONFIG")
    candidates = []
    if env_path:
        candidates.extend(env_path.split(os.pathsep))
    candidates.extend(["/etc/kubernetes/admin.conf", "~/.kube/config"])
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate kubeconfig for a ServiceAccount.")
    parser.add_argument("service_account", help="ServiceAccount name.")
    parser.add_argument(
        "--namespace",
        default="kube-system",
        help="Namespace of the ServiceAccount (default: kube-system).",
    )
    parser.add_argument(
        "--cluster-name",
        help="Override cluster name for the generated kubeconfig.",
    )
    parser.add_argument(
        "--api-server",
        help="Override Kubernetes API server endpoint.",
    )
    parser.add_argument(
        "--kubeconfig",
        type=lambda p: Path(p).expanduser().resolve(),
        help="Path to a kubeconfig file containing cluster metadata.",
    )
    parser.add_argument(
        "--context",
        help="Context name to read from kubeconfig (defaults to current-context).",
    )
    parser.add_argument(
        "--secret-name",
        help="Reuse an existing Secret instead of auto-detecting/creating one.",
    )
    parser.add_argument(
        "--output-dir",
        type=lambda p: Path(p).expanduser().resolve(),
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write the kubeconfig (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="Seconds to wait for the token controller to populate data (default: 30).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        secret_name, secret_data = find_or_create_token_secret(
            args.service_account,
            args.namespace,
            args.secret_name,
            wait_seconds=args.wait_seconds,
        )
    except Exception as exc:
        print(f"[ERROR] Unable to obtain ServiceAccount token: {exc}", file=sys.stderr)
        return 1

    token_b64 = secret_data.get("data", {}).get("token")
    if not token_b64:
        print(
            "[ERROR] Secret data does not contain a token even after waiting.",
            file=sys.stderr,
        )
        return 1
    token = base64.b64decode(token_b64.encode("utf-8")).decode("utf-8")

    ca_from_secret = secret_data.get("data", {}).get("ca.crt")

    cluster_info: Optional[Tuple[str, str, str, bool]] = None

    # Prefer explicit kubeconfig path
    if args.kubeconfig:
        try:
            cluster_info = load_kubeconfig_from_file(
                args.kubeconfig,
                args.context,
                args.cluster_name,
                args.api_server,
            )
        except Exception as exc:
            print(f"[WARN] Failed to read provided kubeconfig: {exc}", file=sys.stderr)
            cluster_info = None

    # Attempt kubectl discovery
    if cluster_info is None:
        try:
            cluster_info = load_kubeconfig_from_kubectl(
                args.context,
                args.cluster_name,
                args.api_server,
            )
        except Exception:
            cluster_info = None

    # Fallback to well-known file if cluster info still missing
    if cluster_info is None:
        fallback_path = preferred_kubeconfig_path()
        if fallback_path:
            try:
                cluster_info = load_kubeconfig_from_file(
                    fallback_path,
                    args.context,
                    args.cluster_name,
                    args.api_server,
                )
            except Exception:
                cluster_info = None

    if cluster_info is None:
        if not (args.cluster_name and args.api_server):
            print(
                "[ERROR] Cluster metadata is unavailable. Provide --cluster-name and "
                "--api-server or a usable --kubeconfig.",
                file=sys.stderr,
            )
            return 1
        cluster_info = (args.cluster_name, args.api_server, "", False)

    cluster_name, api_server, ca_data, insecure_skip_tls = cluster_info

    if not ca_data and not insecure_skip_tls:
        if ca_from_secret:
            ca_data = ca_from_secret
        else:
            print(
                "[ERROR] Unable to determine certificate-authority-data. "
                "Provide a kubeconfig with embedded CA data or enable "
                "--cluster-name/--api-server with a valid kubeconfig.",
                file=sys.stderr,
            )
            return 1

    kubeconfig = build_kubeconfig(
        args.service_account,
        args.namespace,
        cluster_name,
        api_server,
        ca_data,
        token,
        insecure_skip_tls,
    )

    yaml_str = yaml.safe_dump(kubeconfig, sort_keys=False)
    print("---")
    print(yaml_str)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{kubeconfig['current-context']}.yaml"
    output_path.write_text(yaml_str, encoding="utf-8")
    print(f"[INFO] Wrote kubeconfig to {output_path}")
    print(f"[INFO] Token sourced from Secret '{secret_name}' in namespace '{args.namespace}'.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
