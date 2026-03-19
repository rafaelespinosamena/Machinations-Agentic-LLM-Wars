"""Allow running MACHINATIONS as: python -m machinations"""

import sys
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import main

main()
