import os
import sys

# Create a valid path so we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from app.cli.run import main

if __name__ == "__main__":
    main()
