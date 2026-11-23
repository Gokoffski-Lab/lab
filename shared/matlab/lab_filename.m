function name = lab_filename(sub, ses, modality, ext, varargin)
%LAB_FILENAME Build a lab file name from shared/vocab.json.
%   name = lab_filename(sub, ses, modality, ext, 'eye', 'OD', 'stim', 'flash', 'run', 1)
%
%   Convention: sub-<id>_ses-<YYYYMMDD>[_eye-<eye>][_stim-<label>][_run-NN]_<modality>.<ext>
%   ses may be 'YYYY-MM-DD', 'YYYYMMDD' or a datetime. Mirrors shared/python/labnaming.py.

p = inputParser;
addParameter(p, 'eye', '');
addParameter(p, 'stim', '');
addParameter(p, 'run', []);
parse(p, varargin{:});
opt = p.Results;

vocab = jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')), '..', 'vocab.json')));

parts = {['sub-' checkLabel('sub', sub)], ['ses-' sessionStr(ses)]};
if ~isempty(opt.eye)
    parts{end+1} = ['eye-' checkVocab('eye', opt.eye, vocab.eye)];
end
if ~isempty(opt.stim)
    parts{end+1} = ['stim-' checkLabel('stim', opt.stim)];
end
if ~isempty(opt.run)
    r = opt.run;
    if ~isscalar(r) || r ~= fix(r) || r < 1 || r > 99
        error('lab_filename:run', 'run must be an integer 1-99');
    end
    parts{end+1} = sprintf('run-%02d', r);
end
parts{end+1} = checkVocab('modality', modality, vocab.modality);

ext = regexprep(char(ext), '^\.', '');
if isempty(regexp(ext, '^[A-Za-z0-9]+(\.[A-Za-z0-9]+)*$', 'once'))
    error('lab_filename:ext', 'bad extension "%s"', ext);
end
name = [strjoin(parts, '_') '.' ext];
end

function s = checkLabel(field, s)
s = char(s);
if isempty(regexp(s, '^[A-Za-z0-9]+$', 'once'))
    error('lab_filename:label', '%s must be letters/digits only, got "%s"', field, s);
end
end

function s = checkVocab(field, s, allowed)
s = char(s);
if ~any(strcmp(s, allowed))
    error('lab_filename:vocab', '%s "%s" not in vocab.json (allowed: %s)', field, s, strjoin(allowed', ', '));
end
end

function s = sessionStr(ses)
if isdatetime(ses)
    s = char(datetime(ses, 'Format', 'yyyyMMdd'));
    return
end
ses = char(ses);
fmts = {'yyyy-MM-dd', 'yyyyMMdd'};
for k = 1:numel(fmts)
    try
        d = datetime(ses, 'InputFormat', fmts{k});
        if strcmp(char(datetime(d, 'Format', fmts{k})), ses)
            s = char(datetime(d, 'Format', 'yyyyMMdd'));
            return
        end
    catch
    end
end
error('lab_filename:ses', 'session date must be YYYY-MM-DD or YYYYMMDD, got "%s"', ses);
end
