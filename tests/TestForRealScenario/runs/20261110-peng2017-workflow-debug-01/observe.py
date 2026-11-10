"""只读观察本轮真实任务，复用既有留证器。"""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'20261109-peng2017-227-browser'))
import observe as recorder
recorder.ROOT=ROOT
recorder.TASK_ID=json.loads((ROOT/'active-task.json').read_text())['task_id']
recorder.observe()
