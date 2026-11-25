%% Batch convert .pl2 files to .mat files in multiple subfolders
% Each subfolder must begin with a 4-digit experiment ID

clc; clear; close all;
addpath('./MatlabOfflineFilesSDK');

% --- Prompts you for folder with subfolders of .pl2 files 
topFolder = uigetdir(pwd, 'Select top-level folder containing subfolders with .pl2 files');
if isequal(topFolder, 0)
    error('No folder selected.');
end

% --- Parameters ---
num_channels = 64;
offset = 1;

% --- Output root folder ---
outputRoot = fullfile(pwd, 'data/mat');
if ~exist(outputRoot, 'dir')
    mkdir(outputRoot);
end

% --- Find subfolders ---
subFolders = dir(topFolder);
subFolders = subFolders([subFolders.isdir] & ~ismember({subFolders.name}, {'.','..'}));

for s = 1:numel(subFolders)
    inputFolder = fullfile(topFolder, subFolders(s).name);
    [~, folderName] = fileparts(inputFolder);
    tokens = regexp(folderName, '^\d{4}', 'match');

    if isempty(tokens)
        fprintf('Skipping folder (no 4-digit prefix): %s\n', folderName);
        continue;
    end

    exp_name = tokens{1};
    output_name = sprintf('%s_mat', exp_name);
    exportFolder = fullfile(outputRoot, output_name);
    if ~exist(exportFolder, 'dir')
        mkdir(exportFolder);
    end

    % --- Process .pl2 files in this folder ---
    pl2Files = dir(fullfile(inputFolder, '*.pl2'));
    if isempty(pl2Files)
        fprintf('No .pl2 files found in %s. Skipping.\n', inputFolder);
        continue;
    end

    for f = 1:numel(pl2Files)
        pl2Name = pl2Files(f).name;
        [~, baseName, ~] = fileparts(pl2Name);
        filename = fullfile(inputFolder, pl2Name);
        fprintf('Processing %s...\n', pl2Name);

        lfp_struct = struct(); valid_idx = 1;

        % Optional quick plot
        figure('Visible','off','Name', baseName); hold on;

        for i = 1:num_channels
            ch_name = sprintf('FP%02d', i);
            try
                data = PL2Ad(filename, ch_name);
                if isempty(data.Values)
                    continue;
                end
             
                % Reconstruct timestamps
                timestamps = [];
                for frag_i = 1:length(data.FragCounts)
                    count = data.FragCounts(frag_i);
                    ts_start = data.FragTs(frag_i);
                    timestamps = [timestamps, ts_start + (0:count-1)/data.ADFreq];
                end
                
                lfp_struct(valid_idx).channel = ch_name;
                lfp_struct(valid_idx).values = data.Values;
                lfp_struct(valid_idx).timestamps = timestamps(:);
                lfp_struct(valid_idx).sampling_rate = data.ADFreq;

                % Optional signal plot (invisible)
                sig = data.Values + offset * (num_channels - valid_idx);
                plot(sig); text(0, offset * (num_channels - valid_idx), ch_name, 'FontSize', 6);

                valid_idx = valid_idx + 1;
            catch ME
                warning('Could not read %s: %s', ch_name, ME.message);
            end
        end

        hold off; close(gcf);

        % --- Extract event (trigger) timestamps ---
        try
            event_data = PL2EventTs(filename, 'EVT01'); % trigger 
        catch
            warning('No EVT01 found in %s', pl2Name);
            event_data = struct('Ts', []);
        end

        % --- Save output .mat ---
        outFile = fullfile(exportFolder, [baseName '.mat']);
        save(outFile, 'lfp_struct', 'event_data', '-v6');
        fprintf('  → Saved %d channels to %s\n', valid_idx-1, outFile);
    end
end

fprintf('\nBatch conversion complete. All files saved to %s\n', outputRoot);