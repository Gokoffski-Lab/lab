function tests = test_example
%TEST_EXAMPLE Rename and replace with real tests. Run: runtests('<path>/tests')
tests = functiontests(localfunctions);
end

function setupOnce(~)
addpath(fullfile(fileparts(mfilename('fullpath')), '..'));
end

function testPlaceholder(tc)
verifyTrue(tc, true);
end
