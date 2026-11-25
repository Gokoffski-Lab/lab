function tests = test_lab_naming
%TEST_LAB_NAMING Tests for lab_filename.m and lab_eye_code.m.
%   Run from the repo root:  addpath('shared/matlab'); runtests('shared/matlab/tests')
%   Mirrors shared/python/test_labnaming.py.
tests = functiontests(localfunctions);
end

function setupOnce(~)
addpath(fullfile(fileparts(mfilename('fullpath')), '..'));
end

function testFullName(tc)
n = lab_filename('R042', '2026-11-23', 'fvep', 'txt', 'eye', 'OD', 'stim', 'flash', 'run', 1);
verifyEqual(tc, n, 'sub-R042_ses-20261123_eye-OD_stim-flash_run-01_fvep.txt');
end

function testMinimalAndDatetime(tc)
verifyEqual(tc, lab_filename('P7', datetime(2026,1,5), 'erg', '.csv'), 'sub-P7_ses-20260105_erg.csv');
verifyEqual(tc, lab_filename('P7', '20260105', 'erg', 'csv'), 'sub-P7_ses-20260105_erg.csv');
end

function testLegacyEyeMapped(tc)
verifyEqual(tc, lab_filename('R1', '20261123', 'lfp', 'mat', 'eye', 'LE'), 'sub-R1_ses-20261123_eye-OS_lfp.mat');
verifyEqual(tc, lab_filename('R1', '20261123', 'lfp', 'mat', 'eye', 're'), 'sub-R1_ses-20261123_eye-OD_lfp.mat');
end

function testEyeCode(tc)
verifyEqual(tc, lab_eye_code('os'), 'OS');
verifyEqual(tc, lab_eye_code(' OU '), 'OU');
verifyEqual(tc, lab_eye_code('LE'), 'OS');
verifyEqual(tc, lab_eye_code('RE'), 'OD');
verifyError(tc, @() lab_eye_code('L'), 'lab_eye_code:unknown');
verifyError(tc, @() lab_eye_code('_about'), 'lab_eye_code:unknown');
end

function testRejects(tc)
verifyError(tc, @() lab_filename('R_42', '2026-11-23', 'fvep', 'txt'), 'lab_filename:label');
verifyError(tc, @() lab_filename('R42', '11/23/2026', 'fvep', 'txt'), 'lab_filename:ses');
verifyError(tc, @() lab_filename('R42', '2026-02-30', 'fvep', 'txt'), 'lab_filename:ses');
verifyError(tc, @() lab_filename('R42', '2026-11-23', 'FVEP', 'txt'), 'lab_filename:vocab');
verifyError(tc, @() lab_filename('R42', '2026-11-23', 'fvep', 'txt', 'run', 0), 'lab_filename:run');
verifyError(tc, @() lab_filename('R42', '2026-11-23', 'fvep', 'txt', 'stim', '10 Hz'), 'lab_filename:label');
end
