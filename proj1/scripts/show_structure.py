#!/usr/bin/env python3
"""
Generate a visual tree structure of the project
"""

import os

def print_tree(directory, prefix="", max_depth=3, current_depth=0):
    """Print directory tree structure"""
    if current_depth >= max_depth:
        return
    
    try:
        items = sorted(os.listdir(directory))
        # Filter out hidden files and __pycache__
        items = [item for item in items if not item.startswith('.') and item != '__pycache__']
        
        for i, item in enumerate(items):
            path = os.path.join(directory, item)
            is_last = i == len(items) - 1
            
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{item}")
            
            if os.path.isdir(path) and current_depth < max_depth - 1:
                extension_prefix = "    " if is_last else "│   "
                print_tree(path, prefix + extension_prefix, max_depth, current_depth + 1)
    except PermissionError:
        pass

if __name__ == "__main__":
    print("CSE535 Project 1: Distributed Paxos Banking System")
    print("=" * 55)
    print("proj1/")
    print_tree(".", max_depth=3)
