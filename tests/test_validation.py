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

# Test constants
PERFECT_MATCH_TP = 100
PERFECT_MATCH_TN = 50
NO_OVERLAP_FP = 1
NO_OVERLAP_FN = 1
NO_OVERLAP_TN = 98
NO_OVERLAP_AREA_RATIO = 1.0
PARTIAL_TP = 2
PARTIAL_FP = 1
PARTIAL_FN = 1
PARTIAL_TN = 2
PARTIAL_IOU = 0.5
PARTIAL_PRECISION = 2 / 3
PARTIAL_RECALL = 2 / 3
PARTIAL_F1 = 2 / 3
PARTIAL_AREA_RATIO = 1.0
TOLERANCE = 1e-10
PARTIAL_OVERLAP_TP = 2
PARTIAL_OVERLAP_FP = 1
PARTIAL_OVERLAP_FN = 1
PARTIAL_OVERLAP_TN = 2
PARTIAL_OVERLAP_IOU = 0.5
VALID_MASK_TP = 90
VALID_MASK_TN = 0
VALID_MASK_INVALID_ROW = 10
DATACLASS_TP = 10
DATACLASS_FP = 5
DATACLASS_FN = 3
DATACLASS_TN = 100
DATACLASS_IOU = 0.5
DATACLASS_PRECISION = 0.667
DATACLASS_RECALL = 0.769
DATACLASS_F1 = 0.714
DATACLASS_AREA_RATIO = 1.2
DATACLASS_VALID_PIXELS = 118
RGB_GREEN = (0, 255, 0)
RGB_RED = (255, 0, 0)
RGB_BLUE = (0, 0, 255)
RGB_GRAY = (128, 128, 128)
RGB_BLACK = (0, 0, 0)


class TestConfusionMatrix:
    """Tests for confusion matrix computation."""

    def test_perfect_match(self):
        """Perfect match should give TP=all, others=0."""
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == PERFECT_MATCH_TP
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
        assert fp == NO_OVERLAP_FP
        assert fn == NO_OVERLAP_FN
        assert tn == NO_OVERLAP_TN

    def test_partial_overlap(self):
        """Partial overlap should compute correctly."""
        model = np.array([[True, True, False], [False, True, False]])
        ref = np.array([[True, False, False], [False, True, True]])
        valid = np.ones((2, 3), dtype=bool)

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == PARTIAL_OVERLAP_TP
        assert fp == PARTIAL_OVERLAP_FP
        assert fn == PARTIAL_OVERLAP_FN
        assert tn == PARTIAL_OVERLAP_TN

    def test_valid_mask_excludes_invalid(self):
        """Valid mask should exclude pixels from counts."""
        model = np.ones((10, 10), dtype=bool)
        ref = np.ones((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)
        valid[0, :] = False  # First row invalid

        tp, fp, fn, tn = compute_confusion_matrix(model, ref, valid)
        assert tp == VALID_MASK_TP
        assert fp == 0
        assert fn == 0
        # Invalid pixels are excluded, so TN only counts valid dry pixels
        # Here all valid pixels are flooded, so TN = 0
        assert tn == VALID_MASK_TN


class TestMetrics:
    """Tests for metric computation."""

    def test_perfect_match(self):
        """Perfect match should give IoU=1, Precision=1, Recall=1, F1=1."""
        tp, fp, fn, tn = PERFECT_MATCH_TP, 0, 0, PERFECT_MATCH_TN
        metrics = compute_metrics(tp, fp, fn, tn)

        assert metrics.iou == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.area_ratio == 1.0

    def test_no_overlap(self):
        """No true overlap but FP > 0 should give IoU=0, Precision=0, Recall=0, F1=0, Area Ratio = 1.0."""
        tp, fp, fn, tn = 0, NO_OVERLAP_FP, NO_OVERLAP_FN, NO_OVERLAP_TN
        metrics = compute_metrics(tp, fp, fn, tn)

        assert metrics.iou == 0.0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        # Area ratio = (TP + FP) / (TP + FN) = (0 + 1) / (0 + 1) = 1.0
        assert metrics.area_ratio == 1.0

    def test_partial_overlap(self):
        """Partial overlap should compute correctly."""
        # TP=2, FP=1, FN=1, TN=2
        metrics = compute_metrics(PARTIAL_TP, PARTIAL_FP, PARTIAL_FN, PARTIAL_TN)

        # IoU = 2 / (2+1+1) = 0.5
        assert metrics.iou == PARTIAL_IOU
        # Precision = 2 / (2+1) = 2/3
        assert abs(metrics.precision - PARTIAL_PRECISION) < TOLERANCE
        # Recall = 2 / (2+1) = 2/3
        assert abs(metrics.recall - PARTIAL_RECALL) < TOLERANCE
        # F1 = 2 * (2/3) * (2/3) / (4/3) = 2/3
        assert abs(metrics.f1 - PARTIAL_F1) < TOLERANCE
        # Area ratio = (2+1) / (2+1) = 1.0
        assert metrics.area_ratio == PARTIAL_AREA_RATIO

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
        assert metrics.tp == PARTIAL_OVERLAP_TP
        assert metrics.fp == PARTIAL_OVERLAP_FP
        assert metrics.fn == PARTIAL_OVERLAP_FN
        assert metrics.tn == PARTIAL_OVERLAP_TN
        assert metrics.iou == PARTIAL_OVERLAP_IOU


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
        assert np.all(rgb == RGB_GREEN)

    def test_fp_red(self):
        """False positives should be red."""
        model = np.ones((2, 2), dtype=bool)
        ref = np.zeros((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All FP should be red (255, 0, 0)
        assert np.all(rgb == RGB_RED)

    def test_fn_blue(self):
        """False negatives should be blue."""
        model = np.zeros((2, 2), dtype=bool)
        ref = np.ones((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All FN should be blue (0, 0, 255)
        assert np.all(rgb == RGB_BLUE)

    def test_tn_gray(self):
        """True negatives should be gray."""
        model = np.zeros((2, 2), dtype=bool)
        ref = np.zeros((2, 2), dtype=bool)
        valid = np.ones((2, 2), dtype=bool)

        rgb = create_comparison_rgb(model, ref, valid)
        # All TN should be gray (128, 128, 128)
        assert np.all(rgb == RGB_GRAY)

    def test_invalid_black(self):
        """Invalid pixels should be black."""
        model = np.ones((2, 2), dtype=bool)
        ref = np.ones((2, 2), dtype=bool)
        valid = np.array([[True, False], [True, True]])

        rgb = create_comparison_rgb(model, ref, valid)
        # Invalid pixel (0,1) should be black (already zero from initialization)
        assert np.all(rgb[0, 1] == RGB_BLACK)
        # Valid pixels should be green (TP)
        assert np.all(rgb[0, 0] == RGB_GREEN)
        assert np.all(rgb[1, 0] == RGB_GREEN)
        assert np.all(rgb[1, 1] == RGB_GREEN)


class TestValidationMetricsDataclass:
    """Tests for ValidationMetrics dataclass."""

    def test_to_dict(self):
        """to_dict should return all metrics."""
        metrics = ValidationMetrics(
            tp=DATACLASS_TP,
            fp=DATACLASS_FP,
            fn=DATACLASS_FN,
            tn=DATACLASS_TN,
            iou=DATACLASS_IOU,
            precision=DATACLASS_PRECISION,
            recall=DATACLASS_RECALL,
            f1=DATACLASS_F1,
            area_ratio=DATACLASS_AREA_RATIO,
            valid_pixels=DATACLASS_VALID_PIXELS,
        )
        d = metrics.to_dict()
        assert d["tp"] == DATACLASS_TP
        assert d["fp"] == DATACLASS_FP
        assert d["fn"] == DATACLASS_FN
        assert d["tn"] == DATACLASS_TN
        assert d["iou"] == DATACLASS_IOU
        assert d["precision"] == DATACLASS_PRECISION
        assert d["recall"] == DATACLASS_RECALL
        assert d["f1"] == DATACLASS_F1
        assert d["area_ratio"] == DATACLASS_AREA_RATIO
        assert d["valid_pixels"] == DATACLASS_VALID_PIXELS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
