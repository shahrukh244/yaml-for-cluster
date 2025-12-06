#!/usr/bin/env python3
"""
Sync images to local registry with intelligent version handling.

Two types of images supported:
1. SIMPLE IMAGES: 'nginx', 'httpd', 'mysql'
   - Pulls :latest tag
   - Detects actual version inside container
   - Tags/pushes as registry.kube.lan/<image>:<detected_version>
   - Cleans up local :latest tag

2. VERSIONED IMAGES: 'openshift/hello-openshift:v3.9.0', 'ubuntu:24.04'
   - Pulls exact image:tag as specified
   - Pushes to registry with same tag (no version detection)
   - Cleans up original pulled image after push
   - Keeps only the registry-tagged version

ONLY EDIT THE TOP SECTION TO CONFIGURE IMAGES
"""

# ===== USER CONFIGURATION - ONLY EDIT THIS SECTION =====
# Simple images (will pull :latest and detect actual version)
SIMPLE_IMAGES = ['nginx', 'httpd', 'mysql']
# Images with explicit versions/tags (will pull and push exactly as specified)
VERSIONED_IMAGES = ['openshift/hello-openshift:v3.9.0', 'ubuntu:24.04']
REGISTRY = "registry.kube.lan"  # Your local registry
# ===== END USER CONFIGURATION =====

import subprocess
import sys
import re
import json
import os

# Built-in configuration for simple images only (version detection)
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
    """Detect version for simple images only."""
    if image_name not in IMAGE_CONFIG:
        print(f"❌ Unsupported simple image: {image_name}. Supported: {', '.join(IMAGE_CONFIG.keys())}", file=sys.stderr)
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

def image_exists_in_registry(registry, image_name, tag):
    """Check if image exists in registry with specific tag."""
    repo = f"{registry}/{image_name}:{tag}"
    
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

def process_simple_image(image):
    """Process simple images (detect version workflow)."""
    latest_tag = f"{image}:latest"
    print(f"🔄 Processing SIMPLE image: {image}")
    
    try:
        # Pull latest image
        print(f"🐳 Pulling {latest_tag}...")
        run_command(f"docker pull {latest_tag}", capture_output=False)

        # Detect version
        print("🔍 Detecting version...")
        version = get_image_version(image)
        if not version:
            return False
            
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

        return True

    finally:
        # ALWAYS clean up the latest tag for simple images
        print(f"🧹 Cleaning up {latest_tag}")
        run_command(f"docker rmi {latest_tag}", check=False)

def process_versioned_image(full_image):
    """Process versioned images (exact tag workflow)."""
    print(f"🔄 Processing VERSIONED image: {full_image}")
    
    # Parse image name and tag
    if ':' not in full_image:
        print(f"❌ Invalid versioned image format: {full_image}. Must contain a tag (e.g., ubuntu:24.04)", file=sys.stderr)
        return False
    
    image_parts = full_image.split(':', 1)
    source_image = image_parts[0]
    source_tag = image_parts[1]
    
    # Determine target name and tag
    # If image has path (like openshift/hello-openshift), convert to hyphenated name
    # If image is simple (like ubuntu), just use the name
    if '/' in source_image:
        target_name = source_image.replace('/', '-')
        print(f"📝 Converting path: {source_image} → {target_name}")
    else:
        target_name = source_image
    
    try:
        # Pull the exact image
        print(f"🐳 Pulling {full_image}...")
        if run_command(f"docker pull {full_image}", capture_output=False) is None:
            return False
        
        target_image = f"{REGISTRY}/{target_name}:{source_tag}"
        
        # Check if already in registry
        print(f"CallCheck if {target_image} exists...")
        if image_exists_in_registry(REGISTRY, target_name, source_tag):
            print(f"✅ Already exists in registry. Skipping push.")
            return True
        
        # Tag and push
        print(f"🏷️  Tagging as {target_image}")
        if run_command(f"docker tag {full_image} {target_image}") is None:
            return False
        
        print(f"⏫ Pushing to registry...")
        if run_command(f"docker push {target_image}", capture_output=False) is None:
            return False
        
        return True

    finally:
        # ALWAYS clean up the original pulled image for versioned images
        print(f"🧹 Cleaning up {full_image}")
        run_command(f"docker rmi {full_image}", check=False)

def main():
    configure_docker_experimental()

    total_images = len(SIMPLE_IMAGES) + len(VERSIONED_IMAGES)
    print(f"🚀 Starting sync for {total_images} images to {REGISTRY}")
    print(f"Simple images (version detection): {', '.join(SIMPLE_IMAGES)}")
    print(f"Versioned images (exact tags): {', '.join(VERSIONED_IMAGES)}\n")

    failed_images = []
    
    # Process simple images
    for image in SIMPLE_IMAGES:
        print(f"{'='*60}")
        if not process_simple_image(image):
            failed_images.append(f"simple:{image}")
    
    # Process versioned images
    for full_image in VERSIONED_IMAGES:
        print(f"{'='*60}")
        if not process_versioned_image(full_image):
            failed_images.append(f"versioned:{full_image}")

    print(f"\n{'='*60}")
    if failed_images:
        print(f"⚠️  {len(failed_images)}/{total_images} IMAGES FAILED TO SYNC")
        print(f"Failed images: {', '.join(failed_images)}")
        sys.exit(1)
    else:
        print(f"🎉 ALL {total_images} IMAGES SYNCED SUCCESSFULLY TO {REGISTRY}")
        print(f"Simple images: {', '.join(SIMPLE_IMAGES)}")
        print(f"Versioned images: {', '.join(VERSIONED_IMAGES)}")

if __name__ == "__main__":
    main()
