#!/usr/bin/env python
"""
Script to find and print all Python files in a directory tree,
organized by folder.
"""

import os
import argparse
from collections import defaultdict


def find_python_files(base_dir):
    """
    Find all Python files in the directory tree and organize them by folder.
    Ignores virtual environment directories.
    
    Args:
        base_dir: The root directory to search from
        
    Returns:
        A dictionary mapping directory paths to lists of Python files
    """
    python_files_by_dir = defaultdict(list)
    venv_dirs = ['venv', '.venv', 'env', '.env', 'virtualenv', '__pycache__']
    
    for root, dirs, files in os.walk(base_dir):
        # Skip virtual environment directories
        dirs[:] = [d for d in dirs if d not in venv_dirs]
        
        # Check if current directory contains virtual env indicators
        if any(venv_dir in root.split(os.sep) for venv_dir in venv_dirs):
            continue
            
        for file in files:
            if file.endswith('.py'):
                python_files_by_dir[root].append(os.path.join(root, file))
    
    return python_files_by_dir


def print_python_files(python_files_by_dir, base_dir):
    """
    Print Python files organized by directory.
    
    Args:
        python_files_by_dir: Dictionary mapping directories to Python files
        base_dir: The base directory for relative path calculation
    """
    # Sort directories for consistent output
    sorted_dirs = sorted(python_files_by_dir.keys())
    
    current_parent = None
    
    for directory in sorted_dirs:
        # Extract relative path from base_dir for more readable output
        rel_dir = os.path.relpath(directory, base_dir)
        
        # Get the parent directory
        parts = rel_dir.split(os.sep)
        parent = parts[0] if parts[0] != '.' else "Root"
        
        # Print parent header if it has changed
        if parent != current_parent:
            print(f"\n{'=' * 10} {parent} {'=' * 10}")
            current_parent = parent
        
        # Print subdirectory header if not in parent directory
        if len(parts) > 1 and parts[0] != '.':
            subdir = os.path.join(*parts[1:])
            print(f"\n{'-' * 5} {subdir} {'-' * 5}")
        
        # Print files
        for file_path in sorted(python_files_by_dir[directory]):
            print(file_path)


def main():
    parser = argparse.ArgumentParser(description='Find and print Python files by directory')
    parser.add_argument('directory', nargs='?', default=os.getcwd(),
                        help='The directory to search for Python files (default: current directory)')
    parser.add_argument('--exclude', '-e', nargs='+', default=[],
                        help='Additional directories to exclude (e.g., --exclude lib site-packages)')
    args = parser.parse_args()
    
    base_dir = os.path.abspath(args.directory)
    print(f"Searching for Python files in: {base_dir}")
    print(f"Ignoring virtual environments and: {', '.join(args.exclude) if args.exclude else 'no additional directories'}\n")
    
    # Add user-specified directories to ignore
    if hasattr(find_python_files, 'venv_dirs'):
        find_python_files.venv_dirs.extend(args.exclude)
    
    python_files_by_dir = find_python_files(base_dir)
    
    if not python_files_by_dir:
        print("No Python files found.")
        return
    
    print_python_files(python_files_by_dir, base_dir)


if __name__ == "__main__":
    main()