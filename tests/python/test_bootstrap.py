from pathlib import Path

from audioqas import bootstrap


def test_default_options_skip_test_toolchain(tmp_path):
    options = bootstrap.parse_args([])
    plan = bootstrap.build_plan(tmp_path, options)

    assert plan.with_test is False
    assert plan.install_pytest is False
    assert plan.install_node is False
    assert plan.install_playwright is False
    assert plan.python_install_target == "."


def test_with_test_options_include_test_toolchain(tmp_path):
    options = bootstrap.parse_args(["--with-test"])
    plan = bootstrap.build_plan(tmp_path, options)

    assert plan.with_test is True
    assert plan.install_pytest is True
    assert plan.install_node is True
    assert plan.install_playwright is True
    assert plan.python_install_target == ".[dev]"


def test_model_cache_environment_is_repo_local(tmp_path):
    env = bootstrap.model_cache_env(tmp_path)

    assert env["HF_HOME"] == str(tmp_path / ".venv" / "model-cache" / "huggingface")
    assert env["TORCH_HOME"] == str(tmp_path / ".venv" / "model-cache" / "torch")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / ".venv" / "cache")


def test_parse_ffmpeg_version():
    assert bootstrap.parse_ffmpeg_version("ffmpeg version 7.1.1 Copyright") == (7, 1, 1)
    assert bootstrap.parse_ffmpeg_version("ffmpeg version 6.0") == (6, 0, 0)
    assert bootstrap.parse_ffmpeg_version("not ffmpeg") == (0, 0, 0)


def test_ffmpeg_version_requires_six_or_newer():
    assert bootstrap.ffmpeg_version_supported((6, 0, 0)) is True
    assert bootstrap.ffmpeg_version_supported((7, 1, 1)) is True
    assert bootstrap.ffmpeg_version_supported((5, 1, 0)) is False


def test_ensure_ffmpeg_reuses_only_when_ffmpeg_and_ffprobe_exist(monkeypatch, tmp_path):
    installed = []
    paths = {
        "ffmpeg": "/usr/local/bin/ffmpeg",
        "ffprobe": "/usr/local/bin/ffprobe",
    }
    monkeypatch.setattr(bootstrap, "find_executable", lambda name, extra_paths=None: paths.get(name))
    monkeypatch.setattr(bootstrap, "read_command_output", lambda command: "ffmpeg version 7.1.1")
    monkeypatch.setattr(bootstrap, "install_ffmpeg", lambda root: installed.append(root))

    bootstrap.ensure_ffmpeg(tmp_path)

    assert installed == []


def test_ensure_ffmpeg_installs_when_ffprobe_is_missing(monkeypatch, tmp_path):
    installed = []
    paths = {
        "ffmpeg": "/usr/local/bin/ffmpeg",
        "ffprobe": None,
    }
    monkeypatch.setattr(bootstrap, "find_executable", lambda name, extra_paths=None: paths.get(name))
    monkeypatch.setattr(bootstrap, "read_command_output", lambda command: "ffmpeg version 7.1.1")
    monkeypatch.setattr(bootstrap, "install_ffmpeg", lambda root: installed.append(root))

    bootstrap.ensure_ffmpeg(tmp_path)

    assert installed == [tmp_path]


def test_check_only_does_not_install_missing_ffmpeg(monkeypatch, tmp_path):
    installed = []
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: "python3")
    monkeypatch.setattr(bootstrap, "find_executable", lambda name, extra_paths=None: None)
    monkeypatch.setattr(bootstrap, "install_ffmpeg", lambda root: installed.append(root))

    try:
        bootstrap.execute(tmp_path, bootstrap.parse_args(["--check-only"]))
    except RuntimeError as exc:
        assert "ffmpeg" in str(exc)

    assert installed == []


class Recorder:
    def __init__(self):
        self.commands = []

    def run(self, command, *, cwd=None, env=None, check=True):
        self.commands.append((list(command), cwd, env, check))


def test_default_bootstrap_commands_do_not_include_node_or_playwright(tmp_path, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(bootstrap, "run_command", recorder.run)
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: "python3")
    monkeypatch.setattr(bootstrap, "ensure_ffmpeg", lambda root: None)
    monkeypatch.setattr(bootstrap, "warm_models", lambda root, env: None)

    bootstrap.execute(tmp_path, bootstrap.parse_args(["--no-start"]))

    commands = [" ".join(command) for command, *_ in recorder.commands]
    assert any("-m venv .venv" in command for command in commands)
    assert any("-m pip install -e ." in command for command in commands)
    assert not any("npm" in command for command in commands)
    assert not any("playwright" in command for command in commands)


def test_with_test_bootstrap_commands_include_node_and_playwright(tmp_path, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(bootstrap, "run_command", recorder.run)
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: "python3")
    monkeypatch.setattr(bootstrap, "ensure_ffmpeg", lambda root: None)
    monkeypatch.setattr(bootstrap, "warm_models", lambda root, env: None)
    monkeypatch.setattr(bootstrap, "ensure_node", lambda root: None)

    bootstrap.execute(tmp_path, bootstrap.parse_args(["--with-test", "--no-start"]))

    commands = [" ".join(command) for command, *_ in recorder.commands]
    assert any("-m pip install -e .[dev]" in command for command in commands)
    assert any(command == "npm ci" for command in commands)
    assert any("playwright install chromium" in command for command in commands)


def test_nisqa_weights_path_exists():
    assert bootstrap.nisqa_weights_path(Path.cwd()).name == "nisqa.tar"


def test_audio_fixture_path_is_under_tmp(tmp_path):
    assert bootstrap.smoke_audio_path(tmp_path) == tmp_path / ".tmp" / "bootstrap_smoke.wav"


def test_internal_warm_models_runs_all_model_smokes(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bootstrap, "warm_dnsmos", lambda path: calls.append(("dnsmos", path)))
    monkeypatch.setattr(bootstrap, "warm_nisqa", lambda root, path: calls.append(("nisqa", root, path)))
    monkeypatch.setattr(bootstrap, "warm_audiobox", lambda path: calls.append(("audiobox", path)))

    bootstrap.internal_warm_models(tmp_path)

    wav_path = bootstrap.smoke_audio_path(tmp_path)
    assert wav_path.exists()
    assert calls == [
        ("dnsmos", wav_path),
        ("nisqa", tmp_path, wav_path),
        ("audiobox", wav_path),
    ]


def test_main_accepts_internal_warm_models_arg(monkeypatch):
    calls = []
    monkeypatch.setattr(bootstrap, "internal_warm_models", lambda root: calls.append(root))

    bootstrap.main(["--internal-warm-models"])

    assert calls == [Path.cwd()]


def test_main_reads_internal_warm_models_from_sys_argv(monkeypatch):
    calls = []
    monkeypatch.setattr(bootstrap.sys, "argv", ["python", "--internal-warm-models"])
    monkeypatch.setattr(bootstrap, "internal_warm_models", lambda root: calls.append(root))

    bootstrap.main()

    assert calls == [Path.cwd()]


def test_docs_reference_one_click_install_and_with_test():
    root = Path.cwd()
    readme = (root / "README.md").read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")

    assert "https://github.com/Davidwu123/AudioQAS" in readme
    assert "raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh" in readme
    assert "./scripts/audioqas-bootstrap --with-test" in contributing
    assert "./scripts/audioqas-bootstrap --with-test" in agents
    assert ".venv/bin/python -m pip install pytest" not in agents
