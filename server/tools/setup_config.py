#!/usr/bin/env python3
"""
Configuration Setup Tool

This script helps users set up the correct configuration file
by copying one of the profile configurations to config.json.
"""

import os
import sys
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description="Setup configuration for VR Interview System")
    parser.add_argument("--profile", choices=["development", "production", "minimal"],
                      default="development", help="Configuration profile to use")
    parser.add_argument("--no-backup", action="store_true", 
                      help="Don't create a backup of the existing config.json")
    
    args = parser.parse_args()
    
    # Get the project root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(root_dir, "config")
    
    # Check if config directory exists
    if not os.path.exists(config_dir):
        print(f"Error: Config directory not found at {config_dir}")
        return 1
    
    # Source config file path based on profile
    source_config = os.path.join(config_dir, f"config_{args.profile}.json")
    if not os.path.exists(source_config):
        print(f"Error: Profile config not found at {source_config}")
        return 1
    
    # Destination config file path
    dest_config = os.path.join(config_dir, "config.json")
    
    # Create a backup if requested and file exists
    if os.path.exists(dest_config) and not args.no_backup:
        backup_path = os.path.join(config_dir, "config.json.bak")
        try:
            shutil.copy2(dest_config, backup_path)
            print(f"Created backup at {backup_path}")
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
    
    # Copy the profile config to config.json
    try:
        shutil.copy2(source_config, dest_config)
        print(f"Successfully set up {args.profile} configuration")
        print(f"Configuration copied from: {source_config}")
        print(f"Configuration copied to: {dest_config}")
        return 0
    except Exception as e:
        print(f"Error setting up configuration: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
