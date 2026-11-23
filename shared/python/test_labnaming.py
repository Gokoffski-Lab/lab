import datetime as dt

import pytest

from labnaming import build_filename, is_valid, parse_filename


def test_build_full():
    assert (
        build_filename("R042", "2026-11-23", "fvep", "txt", eye="OD", stim="flash", run=1)
        == "sub-R042_ses-20261123_eye-OD_stim-flash_run-01_fvep.txt"
    )


def test_build_minimal_and_date_object():
    assert build_filename("P7", dt.date(2026, 1, 5), "erg", ".csv") == "sub-P7_ses-20260105_erg.csv"


def test_roundtrip():
    name = build_filename("F3", "20261001", "lfp", "nwb", eye="OS", run=12)
    d = parse_filename(name)
    assert d == {"sub": "F3", "ses": "20261001", "eye": "OS", "stim": None, "run": 12,
                 "modality": "lfp", "ext": "nwb"}


def test_multi_part_extension():
    assert parse_filename("sub-R1_ses-20261123_video.ome.tif")["ext"] == "ome.tif"


@pytest.mark.parametrize("kwargs", [
    dict(sub="R_42"),                 # underscore would break parsing
    dict(sub="R42", ses="11/23/2026"),
    dict(sub="R42", ses="2026-02-30"),
    dict(sub="R42", modality="FVEP"),  # case matters
    dict(sub="R42", eye="LE"),         # not in vocab (open decision)
    dict(sub="R42", run=0),
    dict(sub="R42", stim="10 Hz"),
])
def test_build_rejects(kwargs):
    args = dict(sub="R42", ses="2026-11-23", modality="fvep", ext="txt")
    args.update(kwargs)
    sub, ses, modality, ext = args.pop("sub"), args.pop("ses"), args.pop("modality"), args.pop("ext")
    with pytest.raises(ValueError):
        build_filename(sub, ses, modality, ext, **args)


@pytest.mark.parametrize("name", [
    "brainregion_LE_Light_10Hz_50uA_File1.mat",  # legacy pl2_to_mat name
    "sub-R42_ses-20261123_fVEP.txt",
    "sub-R42_ses-20261323_fvep.txt",
    "sub-R42_ses-20261123_eye-XX_fvep.txt",
])
def test_invalid_names(name):
    assert not is_valid(name)
