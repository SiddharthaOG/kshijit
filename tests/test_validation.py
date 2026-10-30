"""Tests for validation utilities."""

from __future__ import annotations

import numpy as np
import pytest

from kshitij_model.validation import (
    ValidationMetrics,
    compute_confusion_matrix,
    compute_metrics,
    compute_metrics_from_arrays,
    create_comparison_rgb,
)


class TestConfusionMatrix:
    """Tests for confusion matrix computation."""

    def test_perfect_match(self):
        """Perfect match should give TP=all, others=0."""
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == 100
        assert fp == 0
        assert fn == 0
        assert tn == 0

    def test_no_overlap(self):
        """No overlap should give FP=model, FN=ref."""
        model = np.zeros((10, 10), dtype=bool)
        model[0, 0] = True
        ref = np.zeros((10, 10), dtype=bool)
        ref[9, 9] = True
        valid = np.ones((10, 10), dtype=bool)

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == 0
        assert fp == 1
        assert fn == 1
        assert tn == 98

    def test_partial_overlap(self):
        """Partial overlap should compute correctly."""
        model = np.array([[True, True, False], [False, True, False]])
        ref = np.array([[True, False, False], [False, True, True]])
        valid = np.ones((2, 3), dtype=bool)

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        # TP: (0,0) and (1,1) = 2
        # FP: (0,1) = 1
        # FN: (1,2) = 1
        # TN: (0,2), (1,0) = 2
        assert tp == 2
        assert fp == 1
        assert fn == 1
        assert tn == 2

    def test_valid_mask_excludes_invalid(self):
        """Valid mask should exclude pixels from counts."""
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)
        valid[0, :] = False  # First row invalid

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == 90  # 100 - 10 invalid
        assert fp == 0
        assert fn == 0
        # Invalid pixels are excluded, so TN only counts valid dry pixels
        # Here all valid pixels are flooded, so TN = 0
        assert tn == 0


class TestMetrics:
    """Tests for metric computation."""

    def test_perfect_match(self):
        """Perfect match should give IoU=1, Precision=1, Recall=1, F1=1."""
        tp, fp, fn, tn = 100, 0, 0, 50
        metrics = compute_metrics(tp, fp, fn, tn)

        assert metrics.iou == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.area_ratio == 1.0

    def test_no_overlap(self):
        """No true overlap but FP > 0 should give IoU=0, Precision=0, Recall=0, F1=0, Area Ratio > 0."""
        tp, fp, fn, tn = 0, 10, 5, 100
        metrics = compute_metrics(tp, fp, fn, tn)

        assert metrics.iou == 0.0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        # Area ratio = (TP + FP) / (TP + FN) = (0 + 10) / (0 + 5) = 2.0
        assert metrics.area_ratio == 2.0

    def test_partial_overlap(self):
        """Partial overlap should compute correctly."""
        # TP=2, FP=1, FN=1, TN=2
        metrics = compute_metrics(2, 1, 1, 2)

        # IoU = 2 / (2+1+1) = 0.5
        assert metrics.iou == 0.5
        # Precision = 2 / (2+1) = 2/3
        assert abs(metrics.precision - 2 / 3) < 1e-10
        # Recall = 2 / (2+1) = 2/3
        assert abs(metrics.recall - 2 / 3) < 1e-10
        # F1 = 2 * (2/3) * (2/3) / (4/3) = 2/3
        assert abs(metrics.f1 - 2 / 3) < 1e-10
        # Area ratio = (2+1) / (2+1) = 1.0
        assert metrics.area_ratio == 1.0

    def test_zero_division_safety(self):
        """All zeros should not raise division by zero."""
        metrics = compute_metrics(0, 0, 0, 0)
        assert metrics.iou == 0.0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        assert metrics.area_ratio == 0.0


class TestComputeMetricsFromArrays:
    """Tests for end-to-end metric computation from arrays."""

    def test_perfect_match(self):
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)

        metrics = compute_metrics_from_arrays(model, ref, valid)
        assert metrics.iou == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_partial_overlap(self):
        model = np.array([[True, True, False], [False, True, False]])
        ref = np.array([[True, False, False], [False, True, True]])
        valid = np.ones((2, 3), dtype=bool)

        metrics = compute_metrics_from_arrays(model, ref, valid)
        assert metrics.tp == 2
        assert metrics.fp == 1
        assert metrics.fn == 1
        assert metrics.tn == 2
        assert metrics.iou == 0.5


class TestComparisonRGB:
    """Tests for RGB comparison composite generation."""

    def test_rgb_shape(self):
        """RGB output should have correct shape."""
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        assert rgb.shape == (10, 10, 3)
        assert rgb.dtype == np.uint8

    def test_tp_green(self):
        """True positives should be green."""
        model = np.ones((2, 2), dtype=bool)
        ref = np.ones((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All TP should be green (0, 255, 0)
        assert np.all(rgb == [0, 255, 0])

    def test_fp_red(self):
        """False positives should be red."""
        model = np.ones((2, 2), dtype=bool)
        ref = np.zeros((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All FP should be red (255, 0, 0)
        assert np.all(rgb == [255, 0, 0])

    def test_fn_blue(self):
        """False negatives should be blue."""
        model = np.zeros((2, 2), dtype=bool)
        ref = np.ones((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All FN should be blue (0, 0, 255)
        assert np.all(rgb == [0, 0, 255])

    def test_tn_gray(self):
        """True negatives should be gray."""
        model = np.zeros((2, 2), dtype=bool)
        ref = np.zeros((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All TN should be gray (128, 128, 128)
        assert np.all(rgb == [128, 128, 128])

    def test_invalid_black(self):
        """Invalid pixels should be black."""
        model = np.ones((2, 2), dtype=bool)
        ref = np.ones((2, 2), dtype=bool)
        valid = np.array([[True, False], [True, True]])

        rgb = create_comparison_rgb(model, ref, valid)
        # Invalid pixel (0,1) should be black (already zero from initialization)
        assert np.all(rgb[0, 1] == [0, 0, 0])
        # Valid pixels should be green (TP)
        assert np.all(rgb[0, 0] == [0, 255, 0])
        assert np.all(rgb[1, 0] == [0, 255, 0])
        assert np.all(rgb[1, 1] == [0, 255, 0])


class TestValidationMetricsDataclass:
    """Tests for ValidationMetrics dataclass."""

    def test_to_dict(self):
        """to_dict should return all metrics."""
        metrics = ValidationMetrics(
            tp=10,
            fp=5,
            fn=3,
            tn=100,
            iou=0.5,
            precision=0.667,
            recall=0.769,
            f1=0.714,
            area_ratio=1.2,
            valid_pixels=118,
        )
        d = metrics.to_dict()
        assert d["tp"] == 10
        assert d["fp"] == 5
        assert d["fn"] == 3
        assert d["tn"] == 100
        assert d["iou"] == 0.5
        assert d["precision"] == 0.667
        assert d["recall"] == 0.769
        assert d["f1"] == 0.714
        assert d["area_ratio"] == 1.2
        assert d["valid_pixels"] == 118


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
