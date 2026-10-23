"""文字彩边伪峰的因果回归：不靠幅值平滑或材料专用坐标。"""
import numpy as np
import pytest
import json
import hashlib
from pathlib import Path
from PIL import Image
from backend.spectra.digitize import LinearAxis, extract_curve, reconstruct


def spectrum(image, *, transpose=False, exclude=()):
    spec = dict(id="trace",kind="alpha2f",projection=None,color="olive",unit="dimensionless",
                roi=[1,1,98,58],frequency_direction="y",amplitude_ticks=[[0,0],[90,3]],exclude=list(exclude))
    if transpose:
        image = image.transpose(1,0,2)
        spec.update(roi=[1,1,58,98],frequency_direction="x")
        spec["exclude"] = [[b,a,d,c] for a,b,c,d in exclude]
    return extract_curve(image,spec,LinearAxis.fit([[1,0],[58,57]]))


@pytest.mark.parametrize("transpose",[False,True])
def test_true_weak_curve_is_not_averaged_with_text_fringes(transpose):
    image=np.full((60,100,3),255,dtype=np.uint8)
    image[5:55,10]=[128,128,0]
    image[30,10]=[187,186,143]  # 真实暗淡曲线；相邻严格颜色像素支持。
    image[30,70]=[105,89,69]    # 本次实图 λ 字形彩边 RGB。
    image[30,85]=[162,143,123]  # 本次实图 ω 字形彩边 RGB。
    result=spectrum(image,transpose=transpose)
    point=next(p for p in result["points"] if p["frequency_pixel"]==30)
    assert point["amplitude_pixel"]==10
    assert point["rejected_chromatic_pixels"]==2
    assert point["detection_mode"]=="chromatic_recovery"
    assert point["status"]=="observed"
    # 单独补模型排除框也应得到同一真正曲线位置。
    masked=spectrum(image,transpose=transpose,exclude=[[65,28,90,32]])
    assert next(p for p in masked["points"] if p["frequency_pixel"]==30)["amplitude_pixel"]==10


def test_disconnected_candidates_are_missing_and_not_interpolated_away():
    image=np.full((60,100,3),255,dtype=np.uint8)
    image[5:55,10]=[128,128,0]
    image[30,75]=[128,128,0]
    result=spectrum(image)
    point=next(p for p in result["points"] if p["frequency_pixel"]==30)
    assert point["observed_amplitude"] is None and point["reconstructed_amplitude"] is None
    assert point["detection_mode"]=="ambiguous_components" and point["candidate_components"]==2
    assert point["reconstruction_blocked"]
    assert reconstruct([1,None,1],max_gap=3,baseline_tolerance=2,max_baseline_gap=10,blocked_indices=[1])[0]==[1,None,1]


def test_genuine_narrow_high_peak_is_preserved_without_amplitude_filtering():
    image=np.full((60,100,3),255,dtype=np.uint8)
    image[5:55,10]=[128,128,0]
    image[30,10:81]=[128,128,0]  # 单行连续真峰，不能按宽度/高度滤掉。
    result=spectrum(image)
    point=next(p for p in result["points"] if p["frequency_pixel"]==30)
    assert point["amplitude_pixel"]==45
    assert point["observed_amplitude"]==pytest.approx(1.5)
    assert point["candidate_components"]==1 and not point["reconstruction_blocked"]


def test_excluded_legend_cannot_supply_support_for_weak_text():
    image=np.full((60,100,3),255,dtype=np.uint8)
    image[5:55,10]=[128,128,0]
    image[30,10]=255
    image[29,70]=[128,128,0]
    image[30,70]=[105,89,69]
    result=spectrum(image,exclude=[[69,28,71,29]])
    point=next(p for p in result["points"] if p["frequency_pixel"]==30)
    assert point["detection_mode"]=="unsupported_chromatic"
    assert point["reconstructed_amplitude"] is None


def test_real_lasc_pixel_regression_with_unchanged_model_calibration():
    folder=Path(__file__).resolve().parents[2]/"docs/specs/154-alpha2f-detail-demo/assets"
    fixture=json.loads((folder/"false-peak-fixture.json").read_text())
    source=folder/fixture["image"]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==fixture["image_sha256"]
    image=np.asarray(Image.open(source).convert("RGB"))
    calibration=fixture["calibration"]
    result=extract_curve(image,calibration,LinearAxis.fit(calibration["frequency_ticks"]))
    point=next(p for p in result["points"] if p["frequency_pixel"]==fixture["frequency_pixel"])
    assert point["amplitude_pixel"]==fixture["expected_amplitude_pixel"]==642
    assert point["rejected_chromatic_pixels"]==2 and point["status"]=="observed"
    # 相邻真实窄峰不被平滑；遮挡引起的多候选明确留空，不插值制造单解。
    neighbor=next(p for p in result["points"] if p["frequency_pixel"]==425)
    assert neighbor["amplitude_pixel"]==648.5
    ambiguous=[p for p in result["points"] if p["detection_mode"]=="ambiguous_components"]
    assert ambiguous and all(p["reconstructed_amplitude"] is None for p in ambiguous)
