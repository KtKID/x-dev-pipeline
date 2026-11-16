#!/usr/bin/env python3
"""Hidden black-box tests for the pinned DeepSeek ACP exercise."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from queue import Empty, Queue
import secrets
import subprocess
import tempfile
from threading import Thread
from time import monotonic, sleep

TIMEOUT = 8


class Client:
    def __init__(self, process):
        self.process = process
        self.incoming = Queue()
        self.frames = []
        self.requests = {}
        self.replies = {}
        self.next_id = 1
        Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.process.stdout:
            self.incoming.put(line)
        self.incoming.put(None)

    def receive(self, deadline):
        try:
            line = self.incoming.get(timeout=max(0, deadline - monotonic()))
        except Empty as error:
            raise AssertionError('ACP response or update timed out') from error
        if line is None:
            return False
        frame = json.loads(line.decode('utf-8'))
        assert isinstance(frame, dict) and frame.get('jsonrpc') == '2.0', frame
        self.frames.append(frame)
        if 'id' in frame:
            i = frame['id']
            assert i in self.requests and i not in self.replies and 'method' not in frame, frame
            assert ('result' in frame) != ('error' in frame), frame
            self.replies[i] = (frame, len(self.frames) - 1)
        else:
            assert frame.get('method') == 'session/update', frame
            assert isinstance(frame.get('params', {}).get('sessionId'), str), frame
            assert isinstance(frame['params'].get('update', {}).get('sessionUpdate'), str), frame
        return True

    def send(self, method, params, *, notify=False):
        frame = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if not notify:
            frame['id'] = i = self.next_id
            self.next_id += 1
            self.requests[i] = len(self.frames)
        self.process.stdin.write((json.dumps(frame) + '\n').encode())
        self.process.stdin.flush()
        return frame.get('id')

    def take(self, i):
        deadline = monotonic() + TIMEOUT
        while i not in self.replies:
            assert self.receive(deadline), f'ACP stdout closed before response {i}'
        return self.replies[i][0]

    def call(self, method, params):
        i = self.send(method, params)
        return self.take(i), i

    def updates(self, i, sid):
        end = self.replies[i][1] if i in self.replies else len(self.frames)
        params = [f['params'] for f in self.frames[self.requests[i]:end] if f.get('method') == 'session/update']
        assert all(p['sessionId'] == sid for p in params), params
        return [p['update'] for p in params]

    def initialize(self, version=1):
        return self.call('initialize', {'protocolVersion': version, 'clientCapabilities': {}})[0]['result']

    def open(self, cwd):
        sid = self.call('session/new', workspace(cwd))[0]['result']['sessionId']
        assert isinstance(sid, str) and sid, sid
        return sid

    def prompt(self, sid, *texts):
        return self.send('session/prompt', {'sessionId': sid, 'prompt': [text(t) for t in texts]})

    def wait_for_chunk(self, i, sid):
        deadline = monotonic() + TIMEOUT
        while not content(self.updates(i, sid), 'agent_message_chunk'):
            assert i not in self.replies and self.receive(deadline), 'prompt ended before streaming'

    def finish(self):
        if not self.process.stdin.closed:
            self.process.stdin.close()
        deadline = monotonic() + TIMEOUT
        while self.receive(deadline):
            pass
        assert self.process.wait(timeout=max(0.1, deadline - monotonic())) == 0, 'ACP process exited nonzero'


def workspace(cwd):
    return {'cwd': str(cwd), 'mcpServers': []}


def text(value):
    return {'type': 'text', 'text': value}


def content(updates, kind):
    return [u['content']['text'] for u in updates if u['sessionUpdate'] == kind]


def stop(client, request, reason):
    frame = client.take(request)
    assert frame.get('result', {}).get('stopReason') == reason, frame


def fixture_events(storage, kind):
    path = storage / 'fixture-events.jsonl'
    if not path.exists():
        return []
    return [row['text'] for row in map(json.loads, path.read_text().splitlines()) if row['type'] == kind]


@contextmanager
def client(project, node, storage, traces, cwd=None):
    cwd = cwd or project
    env = {k: os.environ[k] for k in ('PATH', 'TMPDIR', 'SYSTEMROOT') if k in os.environ}
    env.update(DSH_EVAL_STORAGE=str(storage), TSX_TSCONFIG_PATH=str(project / 'tsconfig.json'))
    loader = (project / 'node_modules/tsx/dist/loader.mjs').as_uri()
    command = [node, '--import', loader, str(project / 'eval-support/start.ts')]
    with tempfile.TemporaryFile() as stderr, subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
    ) as process:
        connection = Client(process)
        try:
            yield connection
            connection.finish()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=TIMEOUT)
            stderr.seek(0)
            traces.append({'cwd': str(cwd), 'stdout': connection.frames,
                           'stderr': stderr.read(4000).decode('utf-8', errors='replace')})


def handshake(open_client, cwd, _storage, _nonce):
    with open_client() as c:
        info = c.initialize(version=999)
        assert info.get('protocolVersion') == 1 and info.get('authMethods', []) == [], info
        caps = info.get('agentCapabilities', {})
        assert caps.get('loadSession') is True and not caps.get('promptCapabilities', {}).get('image'), caps
        for params in (workspace('.'), workspace(cwd.parent), {**workspace(cwd), 'additionalDirectories': [str(cwd.parent)]}):
            assert 'error' in c.call('session/new', params)[0], params
        first = c.send('session/new', workspace(cwd))
        second = c.send('session/new', workspace(cwd))
        results = [c.take(first), c.take(second)]
        assert sum(bool(frame.get('result', {}).get('sessionId')) for frame in results) == 1, results
        assert sum('error' in frame for frame in results) == 1, results


def stream(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        payload = f'你好\n{nonce}'
        i = c.prompt(sid, '你好\n', nonce)
        stop(c, i, 'end_turn')
        updates = c.updates(i, sid)
        chunks = content(updates, 'agent_message_chunk')
        assert len(chunks) >= 2 and ''.join(chunks) == f'Reply: {payload}', chunks
        assert ''.join(content(updates, 'agent_thought_chunk')) == 'Fixture thought', updates
        assert fixture_events(storage, 'generate') == [payload]


def validation(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        for session_id, blocks in (
            (sid, []), (sid, [text('')]),
            (sid, [text(nonce), {'type': 'image', 'mimeType': 'image/png', 'data': 'AA=='}]),
            (f'unknown-{nonce}', [text(nonce)]),
        ):
            assert 'error' in c.call('session/prompt', {'sessionId': session_id, 'prompt': blocks})[0]
        assert fixture_events(storage, 'generate') == []
        stop(c, c.prompt(sid, nonce), 'end_turn')
        assert fixture_events(storage, 'generate') == [nonce]


def tool_updates(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        for payload, expected in ((nonce, 'completed'), (f'fail {nonce}', 'failed')):
            i = c.prompt(sid, f'tool {payload}')
            stop(c, i, 'end_turn')
            updates = c.updates(i, sid)
            start, = [n for n, u in enumerate(updates) if u['sessionUpdate'] == 'tool_call']
            end, = [n for n, u in enumerate(updates) if u['sessionUpdate'] == 'tool_call_update' and u.get('status') in ('completed', 'failed')]
            assert start < end and updates[end]['status'] == expected, updates
            assert updates[start].get('toolCallId') and updates[start]['toolCallId'] == updates[end].get('toolCallId'), updates
        assert fixture_events(storage, 'tool') == [nonce, f'fail {nonce}']


def finish_reasons(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        i = c.prompt(sid, f'limit {nonce}')
        stop(c, i, 'max_tokens')
        assert ''.join(content(c.updates(i, sid), 'agent_message_chunk')) == f'Reply: limit {nonce}'
        assert 'error' in c.take(c.prompt(sid, f'error {nonce}'))
        stop(c, c.prompt(sid, nonce), 'end_turn')
        assert fixture_events(storage, 'generate') == [f'limit {nonce}', f'error {nonce}', nonce]


def cancellation(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        c.send('session/cancel', {'sessionId': sid}, notify=True)
        hanging = f'hang {nonce}'
        i = c.prompt(sid, hanging)
        c.wait_for_chunk(i, sid)
        c.send('session/cancel', {'sessionId': f'unknown-{nonce}'}, notify=True)
        assert 'error' in c.take(c.prompt(sid, 'unexpected second prompt'))
        assert i not in c.replies
        c.send('session/cancel', {'sessionId': sid}, notify=True)
        stop(c, i, 'cancelled')
        deadline = monotonic() + TIMEOUT
        while monotonic() < deadline and hanging not in fixture_events(storage, 'aborted'):
            sleep(0.01)
        assert fixture_events(storage, 'aborted') == [hanging]
        stop(c, c.prompt(sid, nonce), 'end_turn')
        assert fixture_events(storage, 'generate') == [hanging, nonce]


def disconnect(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        i = c.prompt(sid, f'hang {nonce}')
        c.wait_for_chunk(i, sid)
    assert fixture_events(storage, 'aborted') == [f'hang {nonce}'], 'EOF exited without aborting work'


def restore(open_client, cwd, storage, nonce):
    with open_client() as c:
        c.initialize()
        sid = c.open(cwd)
        stop(c, c.prompt(sid, nonce), 'end_turn')
    logs = [list(map(json.loads, p.read_text().splitlines())) for p in (storage / 'sessions').rglob('*.jsonl')]
    assert any(rows and rows[0].get('id') == sid and rows[0].get('cwd') == str(cwd)
               and {'user/message', 'turn/end'} <= {row.get('type') for row in rows[1:]}
               for rows in logs), 'missing durable Harness session log'
    with tempfile.TemporaryDirectory(prefix='acp-other-cwd-') as other_dir:
        other = Path(other_dir).resolve()
        with open_client(other) as c:
            c.initialize()
            assert 'error' in c.call('session/load', {'sessionId': sid, **workspace(other)})[0]
    with open_client() as c:
        c.initialize()
        assert 'error' in c.call('session/load', {'sessionId': 'missing', **workspace(cwd)})[0]
        i = c.send('session/load', {'sessionId': sid, **workspace(cwd)})
        j = c.send('session/load', {'sessionId': sid, **workspace(cwd)})
        assert 'result' in c.take(i) and 'error' in c.take(j)
        updates = c.updates(i, sid)
        assert ''.join(content(updates, 'user_message_chunk')) == nonce, updates
        assert ''.join(content(updates, 'agent_message_chunk')) == f'Reply: {nonce}', updates
        assert fixture_events(storage, 'generate') == [nonce]
        stop(c, c.prompt(sid, f'after {nonce}'), 'end_turn')
        assert fixture_events(storage, 'generate') == [nonce, f'after {nonce}']


CASES = (
    ('ACP-01', 'P0', handshake), ('ACP-02', 'P0', stream),
    ('ACP-03', 'P0', validation), ('ACP-04', 'P1', tool_updates),
    ('ACP-05', 'P0', finish_reasons), ('ACP-06', 'P0', cancellation),
    ('ACP-07', 'P0', disconnect), ('ACP-08', 'P0', restore),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--node', default='node')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    if not __debug__:
        parser.error('运行评分时必须启用 Python assertions')
    executor_root = project.parent if project.parent.name == 'workspace' else project
    if output.is_relative_to(executor_root):
        parser.error('评分产物必须位于考生 workspace 外')
    if not (project / 'node_modules/tsx/dist/loader.mjs').is_file():
        parser.error('缺少 tsx 运行依赖，请先准备评测环境')
    results, evidence = [], {}
    for case_id, severity, check in CASES:
        traces = []
        with tempfile.TemporaryDirectory(prefix='dsh-acp-grade-') as tmp:
            storage = Path(tmp)
            try:
                check(lambda cwd=None: client(project, args.node, storage, traces, cwd),
                      project, storage, secrets.token_hex(6))
                result = {'passed': True}
            except (AssertionError, AttributeError, ValueError, KeyError, OSError, TypeError, subprocess.SubprocessError) as error:
                result = {'passed': False, 'detail': f'{type(error).__name__}: {error}'}
            events = storage / 'fixture-events.jsonl'
            evidence[case_id] = {
                'processes': traces,
                'fixture_events': events.read_text() if events.exists() else '',
                'session_logs': {str(p.relative_to(storage)): p.read_text() for p in (storage / 'sessions').rglob('*.jsonl')},
            }
        results.append({'id': case_id, 'severity': severity, 'evidence': f'wire-evidence.json#{case_id}', **result})
    passed = sum(row['passed'] for row in results)
    result = {'rubric': 'deepseek-acp-v1', 'runtime_passed': passed == len(CASES),
              'critical_gate': all(row['passed'] for row in results if row['severity'] == 'P0'),
              'passed': passed, 'total': len(CASES), 'assertions': results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_name('wire-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'{passed}/{len(CASES)} ACP wire checks: {output}')
    return 0 if result['runtime_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
