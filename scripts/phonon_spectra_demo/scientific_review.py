"""兼容 demo 入口；算法唯一实现位于 backend.spectra。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.spectra.scientific_review import *  # noqa: F401,F403

if __name__ == "__main__":
    main()
