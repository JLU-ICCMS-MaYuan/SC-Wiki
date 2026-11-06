"""原SI完整位点前缀标签的真实失败响应重放。"""
from copy import deepcopy
from pathlib import Path
import json,os,importlib.util
import pytest

def reader():
    path=os.environ.get("SCWIKI_STRUCTURE_CONTEXT_CANDIDATE")
    if path:
        spec=importlib.util.spec_from_file_location("backend.ingest._site_candidate",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    from backend.ingest import structure_reading
    return structure_reading

def fixture():
    return json.loads(Path(__file__).with_name("fixtures").joinpath("yh10-independent-sites.json").read_text())

def test_real_yh10_prefix_sites_expand_without_inventing_original_coordinates():
    data=fixture();original=deepcopy(data["item"])
    output=reader()._validated_candidates({"structures":[data["item"]]},data["catalog"],set(data["imaged_pages"]),data["source"])
    assert len(output)==1 and output[0]["status"]=="valid"
    assert data["item"]==original
    from ase.io import read
    from io import StringIO
    candidate=output[0]
    atoms=read(StringIO(candidate["representations"]["conventional"]["cif"]["text"]),format="cif")
    assert atoms.get_chemical_formula()=="H40Y4" and len(atoms)==44
    assert atoms.cell.lengths()==pytest.approx([4.4788]*3)
    assert all(s["quote"] in [r["content"] for r in data["catalog"].values()] for s in candidate["sources"])

def test_false_coordinate_does_not_pass_with_prefix_label():
    data=fixture();data["item"]["atoms"][1]["coordinates"][0]=0.5
    with pytest.raises(ValueError,match="原子元素或三坐标"):
        reader()._validated_candidates({"structures":[data["item"]]},data["catalog"],set(data["imaged_pages"]),data["source"])
