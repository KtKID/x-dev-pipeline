import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAG_SKILL_DIR = ROOT / "skills" / "x-dev-rag-call"
ADVERSARIAL_RISK_SKILL_DIR = ROOT / "skills" / "x-adversarial-risk"
BUG2RAG_SKILL_DIR = ROOT / "skills" / "x-bug2rag"
RAG_SCRIPT = RAG_SKILL_DIR / "scripts" / "rag_retrieve.py"
RISK_CONTRACT = ADVERSARIAL_RISK_SKILL_DIR / "scripts" / "risk_contract.py"
DEFAULT_CORPUS = (
    ADVERSARIAL_RISK_SKILL_DIR / "references" / "risk-catalog.md"
)
TRIAGE_STORE = BUG2RAG_SKILL_DIR / "scripts" / "triage_store.py"
CORPUS_AGGREGATE = BUG2RAG_SKILL_DIR / "scripts" / "corpus_aggregate.py"
HOME_CORPUS = BUG2RAG_SKILL_DIR / "scripts" / "home_corpus.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CountingEmbedder:
    def __init__(self) -> None:
        self.document_calls = 0
        self.document_batch_sizes: list[int] = []

    def encode_query(self, text: str):
        return [1.0, 0.0]

    def encode_documents(self, texts):
        self.document_calls += 1
        self.document_batch_sizes.append(len(texts))
        return [[1.0, 0.0] for _ in texts]


class RagSkillPortabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag_module = load_module("rag_retrieve_portability", RAG_SCRIPT)
        cls.triage_module = load_module("triage_store_portability", TRIAGE_STORE)

    def run_external(self, *command: str):
        with tempfile.TemporaryDirectory() as raw:
            return subprocess.run(
                [*command],
                cwd=raw,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_rag_script_entrypoint_works_outside_plugin_repo(self):
        result = self.run_external(sys.executable, str(RAG_SCRIPT), "--help")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--source", result.stdout)
        self.assertIn("--model", result.stdout)

    def test_risk_contract_and_default_corpus_work_outside_plugin_repo(self):
        result = self.run_external(
            sys.executable,
            str(RISK_CONTRACT),
            "validate-corpus",
            str(DEFAULT_CORPUS),
            "--require-rich-fields",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_triage_defaults_to_home_corpus_and_remains_overridable(self):
        self.assertEqual(
            self.triage_module.BUG2RAG_SKILL_DIR,
            BUG2RAG_SKILL_DIR,
        )
        self.assertFalse(
            hasattr(self.triage_module, "ADVERSARIAL_RISK_SKILL_DIR")
        )
        self.assertEqual(
            self.triage_module.DEFAULT_TARGET,
            Path.home() / ".x-dev-pipeline" / "rag" / "risk-catalog.md",
        )

        result = self.run_external(
            sys.executable,
            str(TRIAGE_STORE),
            "--target",
            str(DEFAULT_CORPUS),
            "--keywords",
            "测试、路径",
            "--risk",
            "调用目录变化时，固定相对路径会定位到错误资源。",
            "--scene",
            "插件从任意外部项目目录运行。",
            "--wrong",
            "以当前工作目录拼接插件资源路径。",
            "--correct",
            "以当前 skill 目录拼接脚本和默认语料。",
            "--observable",
            "外部目录运行时仍能生成预览。",
            "--category",
            "边界/默认值",
            "--dry-run",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["preview_id"], "AR-007")

        validated = self.run_external(
            sys.executable,
            str(CORPUS_AGGREGATE),
            "validate-flat",
            "--target",
            str(DEFAULT_CORPUS),
            "--json",
        )
        self.assertEqual(
            validated.returncode,
            0,
            validated.stdout + validated.stderr,
        )
        self.assertTrue(json.loads(validated.stdout)["valid"])

    def test_home_corpus_entrypoint_works_outside_plugin_repo(self):
        result = self.run_external(
            sys.executable,
            str(HOME_CORPUS),
            "path",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["target"],
            str(
                Path.home()
                / ".x-dev-pipeline"
                / "rag"
                / "risk-catalog.md"
            ),
        )

    def test_directory_retrieval_encodes_all_documents_in_one_batch(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "a.md").write_text(
                "## AR-001\n\nRisk：状态恢复失败。\n",
                encoding="utf-8",
            )
            (directory / "b.md").write_text(
                "## AR-002\n\nRisk：幂等请求重复。\n",
                encoding="utf-8",
            )
            chunks = self.rag_module.load_chunks(directory)
            embedder = CountingEmbedder()
            matches = self.rag_module.retrieve(
                chunks,
                "状态恢复与幂等",
                2,
                embedder,
            )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(matches), 2)
        self.assertEqual(embedder.document_calls, 1)
        self.assertEqual(embedder.document_batch_sizes, [2])

    def test_skill_commands_do_not_embed_repo_or_interpreter_paths(self):
        skill_files = (
            RAG_SKILL_DIR / "SKILL.md",
            ADVERSARIAL_RISK_SKILL_DIR / "SKILL.md",
            BUG2RAG_SKILL_DIR / "SKILL.md",
            ROOT / "skills" / "x-spec" / "SKILL.md",
            ROOT / "skills" / "x-req" / "SKILL.md",
        )
        forbidden = (
            "/opt/homebrew/",
            "/Volumes/",
            "python skills/",
            "python3 skills/",
        )
        for path in skill_files:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                for marker in forbidden:
                    self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
