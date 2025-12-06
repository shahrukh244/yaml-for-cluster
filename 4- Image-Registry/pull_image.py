#!/usr/bin/env python3
"""
Sync multiple latest images to local registry with version tags.
ONLY EDIT THE TOP SECTION TO ADD/REMOVE IMAGES
"""

# ===== USER CONFIGURATION - ONLY EDIT THIS SECTION =====
IMAGES_TO_SYNC = ['nginx', 'httpd', 'mysql']  # ADD YOUR IMAGE NAMES HERE
REGISTRY = "registry.kube.lan"  # Your local registry
# ===== END USER CONFIGURATION =====

import subprocess
import sys
import re
import json
import os

# Built-in configuration for common images (pre-verified in your environment)
IMAGE_CONFIG = {
    "nginx": {
        "version_cmd": "nginx -v",
        "version_pattern": r'version: [^/]+/([\d.]+[a-z]*)'
    },
    "httpd": {
        "version_cmd": "httpd -v",
        "version_pattern": r'Apache/([\d.]+)'
    },
    "mysql": {
        "version_cmd": "mysqld --version",
        "version_pattern": r'Ver\s+([\d.]+)'
    },
    "alpine": {
        "version_cmd": "cat /etc/alpine-release",
        "version_pattern": r'([\d.]+)'
    },
    "redis": {
        "version_cmd": "redis-server --version",
        "version_pattern": r'version=(\d+\.\d+\.\d+)'
    },
    "ubuntu": {
        "version_cmd": "grep VERSION_ID /etc/os-release",
        "version_pattern": r'VERSION_ID="([\d.]+)"'
    }
}

def run_command(cmd, capture_output=True, check=True):
    """Run shell command with combined stdout/stderr capture."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=check
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if "no such manifest" in e.output.lower():
            return None
        if not check:
            return None
        print(f"❌ Command failed: {cmd}\nError output:\n{e.output}", file=sys.stderr)
        return None

def get_image_version(image_name):
    """Automatically detect version using built-in configurations."""
    if image_name not in IMAGE_CONFIG:
        print(f"❌ Unsupported image: {image_name}. Supported: {', '.join(IMAGE_CONFIG.keys())}", file=sys.stderr)
        return None
    
    config = IMAGE_CONFIG[image_name]
    cmd = f"docker run --rm {image_name}:latest {config['version_cmd']}"
    output = run_command(cmd, check=False)
    
    if not output:
        print(f"❌ No output from version command for {image_name}", file=sys.stderr)
        return None
    
    match = re.search(config['version_pattern'], output)
    if match:
        return match.group(1)
    else:
        print(f"❌ Failed to extract version for {image_name}. Output:\n{output}", file=sys.stderr)
        return None

def image_exists_in_registry(registry, image_name, version):
    """Check if image exists in registry."""
    repo = f"{registry}/{image_name}:{version}"
    
    # Try manifest inspect first
    manifest_cmd = f"docker manifest inspect {repo} >/dev/null 2>&1"
    try:
        subprocess.run(manifest_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        pass
    
    # Fallback to local inspect
    inspect_cmd = f"docker inspect {repo} >/dev/null 2>&1"
    try:
        subprocess.run(inspect_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def configure_docker_experimental():
    """Silently enable Docker experimental features."""
    config_path = os.path.expanduser("~/.docker/config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
                if config.get("experimental") == "enabled":
                    return
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump({"experimental": "enabled"}, f)

def main():
    configure_docker_experimental()

    print(f"🚀 Starting sync for {len(IMAGES_TO_SYNC)} images to {REGISTRY}")
    print(f"SupportedContent: {', '.join(IMAGE_CONFIG.keys())}")
    print(f"Selected images: {', '.join(IMAGES_TO_SYNC)}\n")

    any_failed = False
    for image in IMAGES_TO_SYNC:
        latest_tag = f"{image}:latest"
        print(f"{'='*50}")
        print(f"🔄 Processing: {image}")
        
        try:
            # Pull latest image
            print(f"🐳 Pulling {latest_tag}...")
            run_command(f"docker pull {latest_tag}", capture_output=False)

            # Detect version
            print("🔍 Detecting version...")
            version = get_image_version(image)
            if not version:
                any_failed = True
                continue
                
            print(f"✅ Detected version: {version}")

            target_image = f"{REGISTRY}/{image}:{version}"

            # Check registry and push if needed
            print(f"CallCheck if {target_image} exists...")
            if image_exists_in_registry(REGISTRY, image, version):
                print(f"✅ Already exists in registry. Skipping push.")
            else:
                print(f"🏷️  Tagging as {target_image}")
                run_command(f"docker tag {latest_tag} {target_image}")
                
                print(f"⏫ Pushing to registry...")
                run_command(f"docker push {target_image}", capture_output=False)

        finally:
            # ALWAYS clean up the latest tag, even on failure
            print(f"🧹 Cleaning up {latest_tag}")
            run_command(f"docker rmi {latest_tag}", check=False)

    print(f"\n{'='*50}")
    if any_failed:
        print("⚠️  SOME IMAGES FAILED TO SYNC - CHECK LOGS ABOVE")
        sys.exit(1)
    else:
        print(f"🎉 ALL IMAGES SYNCED SUCCESSFULLY TO {REGISTRY}")
        print(f"Images processed: {', '.join(IMAGES_TO_SYNC)}")

if __name__ == "__main__":
    main()
