function code = lab_eye_code(in)
%LAB_EYE_CODE Return the canonical eye code (OD, OS or OU) from shared/vocab.json.
%   lab_eye_code('os')  -> 'OS'
%   lab_eye_code('LE')  -> 'OS'   (legacy pl2_to_mat.m code: LE = left = OS)
%   lab_eye_code('RE')  -> 'OD'   (legacy: RE = right = OD)
%   Errors on anything else. Never write LE/RE into new file names.

vocab = jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')), '..', 'vocab.json')));
code = upper(strtrim(char(in)));

if any(strcmp(code, vocab.eye))
    return
end
if isvarname(code) && isfield(vocab.legacy_eye_map, code) && code(1) ~= '_'
    code = vocab.legacy_eye_map.(code);
    return
end
error('lab_eye_code:unknown', 'unknown eye code "%s" (allowed: %s; legacy: LE, RE)', ...
    char(in), strjoin(vocab.eye', ', '));
end
