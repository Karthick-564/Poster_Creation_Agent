"""Unit tests for background OCR & pseudo-text detection gate."""
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image
import pytest

from poster_agent.qa.gates import check_background_ocr


def test_clean_background_passes():
    """A clean gradient or solid canvas must pass check_background_ocr with 0 failures."""
    im = Image.new("RGB", (400, 500), "#070B19")
    failures = check_background_ocr(im)
    assert len(failures) == 0


def test_baked_pseudo_text_detected_via_ocr():
    """When OCR detects unmapped words in background, gate flags failure."""
    im = Image.new("RGB", (400, 500), "#070B19")
    
    mock_tess = MagicMock()
    mock_tess.image_to_string.return_value = "Clomailioka 2030 FESTIVAL"
    
    with patch.dict(sys.modules, {"pytesseract": mock_tess}):
        failures = check_background_ocr(im)
        assert len(failures) == 1
        assert failures[0].kind == "background_ocr"
        assert "clomailioka" in failures[0].measured["detected_tokens"]


def test_allowed_words_filter_matches():
    """If detected words match brief allowed words, they are not flagged as pseudo-text."""
    im = Image.new("RGB", (400, 500), "#070B19")
    
    mock_tess = MagicMock()
    mock_tess.image_to_string.return_value = "NOIR BEATS 2026"
    
    with patch.dict(sys.modules, {"pytesseract": mock_tess}):
        failures = check_background_ocr(im, allowed_words=["NOIR", "BEATS", "2026"])
        assert len(failures) == 0


def test_deterministic_heuristic_detects_dense_text_block():
    """When OCR is unavailable, dense high-frequency glyph pattern triggers heuristic."""
    arr = np.zeros((400, 400, 3), dtype=np.uint8)
    # Paint high-frequency text-like patterns across multiple blocks
    for y in range(40, 360, 20):
        for x in range(30, 370, 6):
            arr[y : y + 10, x : x + 3] = 240

    im = Image.fromarray(arr)
    # Ensure pytesseract is absent from sys.modules
    with patch.dict(sys.modules, {"pytesseract": None}):
        failures = check_background_ocr(im)
        assert len(failures) >= 1
        assert failures[0].kind == "background_ocr"
        assert failures[0].measured["source"] == "heuristic_edge_crossings"
