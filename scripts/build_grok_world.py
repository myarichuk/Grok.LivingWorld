import os
import re

def combine_files(src_dir, output_file):
    """
    Combines all Python files in the src directory into a single file.
    """
    
    # Order matters for dependencies
    file_order = [
        "models.py",
        "dice.py",
        "storage.py"
    ]
    
    combined_content = []
    
    # Add imports that might be missing due to file merging
    # We'll just add standard library imports at the top
    combined_content.append("import uuid")
    combined_content.append("import random")
    combined_content.append("import re")
    combined_content.append("import json")
    combined_content.append("from datetime import datetime")
    combined_content.append("from typing import List, Dict, Optional, Any, Set, Union")
    combined_content.append("from collections import defaultdict")
    combined_content.append("from dataclasses import dataclass, field, asdict")
    combined_content.append("from enum import Enum")
    combined_content.append("\n")

    for filename in file_order:
        filepath = os.path.join(src_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read()
                
                # Remove local imports (e.g., from .models import ...)
                content = re.sub(r"from \.[\w]+ import .+\n", "", content)
                # Remove standard imports as we added them at the top
                content = re.sub(r"import .+\n", "", content)
                content = re.sub(r"from [\w]+ import .+\n", "", content)
                
                combined_content.append(f"# --- {filename} ---")
                combined_content.append(content)
                combined_content.append("\n")
                
    # Add bootstrap function
    combined_content.append("# --- Bootstrap ---")
    combined_content.append("\n")
    combined_content.append("def bootstrap():")
    combined_content.append('    """Returns a fresh WorldLog instance ready for use."""')
    combined_content.append("    return WorldLog()")
    combined_content.append("\n")
    
    # Write to file
    with open(output_file, "w") as f:
        for line in combined_content:
            f.write(line)
            if not line.endswith('\n'):
                f.write('\n')
        
    print(f"Successfully created {output_file}")

if __name__ == "__main__":
    # Adjust paths based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, "../src/world_log")
    output_file = os.path.join(script_dir, "../grok_world.py")

    combine_files(src_dir, output_file)
