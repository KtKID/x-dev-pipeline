#!/usr/bin/env python3
"""Prepare one DeepSeek ACP Eval arm without exporting Git history or grading inputs."""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCHMARK = REPO / 'skills/pipeline-efficiency-benchmark/scripts'
PUBLIC = REPO / 'evals/problems/deepseek-acp'
BASE = 'add59a3336f0ab61c55499418081aab76cb550f8'
EXTRA = ('x-explore-for-spec', 'x-tech-design', 'x-verify-tech')
sys.path.insert(0, str(BENCHMARK))

from benchmark_common import BenchmarkError, REQUIRED_SKILLS, read_json, sha256_file, tree_hashes, write_json
from prepare_workspace import prepare
from validate_workspace import validate_workspace


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args])


def export(root: Path, ref: str, target: Path, *, skills: bool = False) -> None:
    paths = ['skills/' + name for name in (*REQUIRED_SKILLS, *EXTRA)] if skills else []
    data = git(root, 'archive', '--format=tar', ref, *paths)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for entry in archive:
            path = Path(entry.name)
            if not entry.isfile() or path.is_absolute() or '..' in path.parts:
                continue
            if not skills and (
                path.parts[0] in {'.agents', '.claude', '.github'}
                or path.is_relative_to('docs/rfc')
            ):
                continue
            dest = target / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(entry) as source, dest.open('xb') as output:
                shutil.copyfileobj(source, output)
            dest.chmod(entry.mode & 0o777)


def assert_regular_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise BenchmarkError(f'输入根目录必须是真实目录：{root}')
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise BenchmarkError(f'输入只能包含普通文件和目录：{path}')


def copy_offline_tsx(harness: Path, project: Path) -> dict[str, str]:
    """Copy the host-platform tsx runtime, never the checkout's module tree."""
    tsx = (harness / 'node_modules/tsx').resolve(strict=True)
    esbuild = (tsx.parent / 'esbuild').resolve(strict=True)
    arch = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine(), platform.machine())
    binary = f'@esbuild/{platform.system().lower()}-{arch}'
    sources = {'tsx': tsx, 'esbuild': esbuild, binary: (esbuild.parent / binary).resolve(strict=True)}
    versions = {}
    for name, source in sources.items():
        assert_regular_tree(source)
        metadata = read_json(source / 'package.json')
        if metadata.get('name') != name:
            raise BenchmarkError(f'离线依赖名称不匹配：{source}')
        versions[name] = metadata['version']
        shutil.copytree(source, project / 'node_modules' / name)
    return versions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', required=True, type=Path, help='本机 DeepSeek Harness 源码库')
    parser.add_argument('--run-dir', required=True, type=Path, help='两个源码库之外的新目录')
    parser.add_argument('--pipeline-ref', help='冻结的 pipeline Git ref；省略则使用当前工作区，包括未提交 skill')
    parser.add_argument('--offline-tsx', action='store_true', help='从本机 Harness 安装复制 tsx、esbuild 和本机平台二进制')
    args = parser.parse_args()

    harness, run = args.harness.resolve(), args.run_dir.resolve()
    if any(run == root or run.is_relative_to(root) for root in (REPO, harness)):
        parser.error('run 目录必须在两个源码库之外')
    try:
        pipeline_commit = git(REPO, 'rev-parse', '--verify', '--end-of-options', f'{args.pipeline_ref or "HEAD"}^{{commit}}').decode().strip()
        assert_regular_tree(PUBLIC)
        with tempfile.TemporaryDirectory(prefix='dsh-acp-input-') as temp:
            stage = Path(temp)
            task = stage / 'task'
            export(harness, BASE, task)
            shutil.copytree(PUBLIC / 'eval-support', task / 'eval-support')
            versions = copy_offline_tsx(harness, task) if args.offline_tsx else {}
            if args.pipeline_ref:
                export(REPO, pipeline_commit, stage, skills=True)
                skills = stage / 'skills'
            else:
                skills = REPO / 'skills'
            for name in (*REQUIRED_SKILLS, *EXTRA):
                if not (skills / name / 'SKILL.md').is_file():
                    raise BenchmarkError(f'缺少 skill：{name}')
                assert_regular_tree(skills / name)
            assert_regular_tree(task)
            run.mkdir(parents=True)
            workspace = run / 'workspace'
            for name in (*REQUIRED_SKILLS, *EXTRA):
                shutil.copytree(
                    skills / name, workspace / 'skills' / name,
                    ignore=shutil.ignore_patterns('evals', 'tests', '__pycache__', '*.pyc', '.git', '.DS_Store'),
                )
            result = prepare(
                workspace, task, None, PUBLIC / 'PROMPT.md', skills,
                None, 'public_task_only', True,
            )
            (workspace / 'skills/README.md').write_text(
                '# 本地 Pipeline\n\n'
                '依次读取各阶段目录的 `SKILL.md`。阶段产物和实现都写入 `task/`；'
                '按本地文档判断风险复核和修复是否适用。\n\n'
                '`x-explore` → `x-spec` → 需求确认 → `x-tech-design` → 设计确认 → '
                '`x-req` → `x-dev` → `x-verify-spec` / `x-verify-tech` → `x-qa-gate`。\n\n'
                '`x-adversarial-risk` 和 `x-fix` 按需使用，`x-dev-rag-call` 为共享依赖。\n',
                encoding='utf-8',
            )
            manifest_path = Path(result['manifest'])
            manifest = read_json(manifest_path)
            manifest['files'] = tree_hashes(workspace)
            manifest['skills'] = [
                {'name': name, 'sha256': sha256_file(workspace / 'skills' / name / 'SKILL.md')}
                for name in (*REQUIRED_SKILLS, *EXTRA)
            ]
            manifest['public_inputs'] = [{'target': 'task'}, {'target': 'PROMPT.md'}]
            manifest.pop('skills_root', None)
            manifest.update(
                case='deepseek-acp-v1', scope='full_pipeline', task_commit=BASE,
                pipeline_commit=pipeline_commit,
                pipeline_input='git' if args.pipeline_ref else 'worktree',
                offline_runtime=versions,
            )
            write_json(manifest_path, manifest)
            assert_regular_tree(workspace)
            issues = validate_workspace(workspace, manifest_path)
            xdev = subprocess.run(
                [sys.executable, str(workspace / 'skills/x-dev/scripts/xdev.py'), '--help'],
                cwd=workspace / 'task', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, text=True, timeout=20,
            )
            if xdev.returncode:
                issues.append({'code': 'ACP_XDEV', 'message': xdev.stderr[-1000:]})
            write_json(run / 'preflight.json', {'valid': not issues, 'issues': issues})
            if issues:
                raise BenchmarkError(f'preflight 失败：{issues}')
            print(json.dumps({'workspace': str(workspace), 'manifest': str(manifest_path), 'valid': True}, ensure_ascii=False))
    except (OSError, subprocess.SubprocessError, BenchmarkError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
