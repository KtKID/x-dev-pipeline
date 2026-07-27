import contextlib
import io
import json
import math
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "x-adversarial-risk" / "scripts"
SCRIPT = SCRIPTS / "risk_retrieve.py"
CATALOG = (
    ROOT
    / "tests"
    / "fixtures"
    / "risk-catalog.md"
)

sys.path.insert(0, str(SCRIPTS))
import risk_retrieve  # noqa: E402
from risk_contract import RiskCard, parse_catalog  # noqa: E402


class FixedEmbedding:
    def __init__(self, vectors):
        self.query_vector = vectors[0]
        self.document_vectors = vectors[1:]

    def encode_query(self, _text):
        return self.query_vector

    def encode_documents(self, texts):
        if len(texts) != len(self.document_vectors):
            raise AssertionError("测试向量数量与输入数量不一致")
        return self.document_vectors


class UncheckedEmbedding:
    def __init__(self, vectors):
        self.query_vector = vectors[0]
        self.document_vectors = vectors[1:]

    def encode_query(self, _text):
        return self.query_vector

    def encode_documents(self, _texts):
        return self.document_vectors


class RiskRetrieveTest(unittest.TestCase):
    def setUp(self):
        self.cards, issues = parse_catalog(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(issues, [])

    def run_main(self, args, vectors=None, factory=None):
        if factory is None:
            factory = lambda _model: FixedEmbedding(vectors)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = risk_retrieve.main(args, embedder_factory=factory)
        return code, json.loads(output.getvalue())

    def run_subprocess(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_top_one_has_only_id_and_text(self):
        vectors = [
            [1.0, 0.0],
            [0.1, 0.9],
            [0.2, 0.8],
            [1.0, 0.0],
            [0.3, 0.7],
            [0.4, 0.6],
        ]
        code, payload = self.run_main(
            [
                "query",
                "--catalog",
                str(CATALOG),
                "--keywords",
                "日志恢复、状态迁移",
                "--risk",
                "校验和正确但状态转换非法",
                "--json",
            ],
            vectors=vectors,
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["matches"]), 1)
        self.assertEqual(payload["matches"][0]["id"], "AR-003")
        self.assertEqual(set(payload["matches"][0]), {"id", "text"})

    def test_top_n_larger_than_catalog_returns_all_cards(self):
        vectors = [[1.0, 0.0], *([[1.0, 0.0]] * len(self.cards))]
        matches = risk_retrieve.retrieve(
            self.cards,
            "功能",
            "风险",
            10,
            FixedEmbedding(vectors),
        )
        self.assertEqual(len(matches), len(self.cards))

    def test_equal_scores_use_id_order(self):
        cards = [
            RiskCard("AR-002", "b", "b-risk"),
            RiskCard("AR-001", "a", "a-risk"),
        ]
        matches = risk_retrieve.retrieve(
            cards,
            "query",
            "risk",
            2,
            FixedEmbedding([[1.0], [1.0], [1.0]]),
        )
        self.assertEqual(
            [card.id for card in matches],
            ["AR-001", "AR-002"],
        )

    def test_invalid_top_n_returns_minimal_error(self):
        code, payload = self.run_main(
            [
                "query",
                "--catalog",
                str(CATALOG),
                "--keywords",
                "日志",
                "--risk",
                "状态非法",
                "--top-n",
                "0",
                "--json",
            ],
            vectors=[],
        )
        self.assertEqual(code, 2)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "INVALID_ARGUMENT")

    def test_non_integer_top_n_returns_json_error_from_real_cli(self):
        result = self.run_subprocess(
            "query",
            "--catalog",
            str(CATALOG),
            "--keywords",
            "日志",
            "--risk",
            "状态非法",
            "--top-n",
            "abc",
            "--json",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "INVALID_ARGUMENT")

    def test_missing_required_argument_returns_json_error_from_real_cli(self):
        result = self.run_subprocess(
            "query",
            "--catalog",
            str(CATALOG),
            "--keywords",
            "日志",
            "--json",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "INVALID_ARGUMENT")

    def test_empty_keywords_and_risk_exit_two(self):
        base = [
            "query",
            "--catalog",
            str(CATALOG),
            "--keywords",
            "日志",
            "--risk",
            "状态非法",
            "--json",
        ]
        for field_index in (4, 6):
            args = list(base)
            args[field_index] = " "
            code, payload = self.run_main(args, vectors=[])
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"], "INVALID_ARGUMENT")

    def test_missing_catalog_path_exits_two(self):
        with tempfile.TemporaryDirectory() as raw:
            code, payload = self.run_main(
                [
                    "query",
                    "--catalog",
                    str(Path(raw) / "missing.md"),
                    "--keywords",
                    "日志",
                    "--risk",
                    "状态非法",
                    "--json",
                ],
                vectors=[],
            )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "IO_ERROR")

    def test_empty_catalog_exits_one_before_model_load(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "catalog.md"
            path.write_text("# empty\n", encoding="utf-8")

            def fail_if_called(_model):
                raise AssertionError("空语料不应加载模型")

            code, payload = self.run_main(
                [
                    "query",
                    "--catalog",
                    str(path),
                    "--keywords",
                    "日志",
                    "--risk",
                    "状态非法",
                    "--json",
                ],
                factory=fail_if_called,
            )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "INVALID_CATALOG")

    def test_invalid_catalog_exits_one_before_model_load(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "catalog.md"
            path.write_text("## AR-001\n\n关键词：日志\n", encoding="utf-8")

            def fail_if_called(_model):
                raise AssertionError("格式失败时不应加载模型")

            code, payload = self.run_main(
                [
                    "query",
                    "--catalog",
                    str(path),
                    "--keywords",
                    "日志",
                    "--risk",
                    "状态非法",
                    "--json",
                ],
                factory=fail_if_called,
            )
        self.assertEqual(code, 1)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "INVALID_CATALOG")

    def test_model_load_failure_returns_exit_two(self):
        def fail_model(_model):
            raise RuntimeError("本地模型缺失")

        code, payload = self.run_main(
            [
                "query",
                "--catalog",
                str(CATALOG),
                "--keywords",
                "日志",
                "--risk",
                "状态非法",
                "--json",
            ],
            factory=fail_model,
        )
        self.assertEqual(code, 2)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "MODEL_ERROR")

    def test_vector_count_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "向量数量"):
            risk_retrieve.retrieve(
                self.cards,
                "功能",
                "风险",
                1,
                UncheckedEmbedding([[1.0]]),
            )

    def test_vector_dimension_and_empty_vector_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "维度不一致或为空"):
            risk_retrieve.retrieve(
                self.cards[:1],
                "功能",
                "风险",
                1,
                UncheckedEmbedding([[1.0, 0.0], [1.0]]),
            )
        with self.assertRaisesRegex(ValueError, "维度不一致或为空"):
            risk_retrieve.retrieve(
                self.cards[:1],
                "功能",
                "风险",
                1,
                UncheckedEmbedding([[], []]),
            )

    def test_non_finite_similarity_is_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaisesRegex(ValueError, "有限数值"):
                risk_retrieve.retrieve(
                    self.cards[:1],
                    "功能",
                    "风险",
                    1,
                    UncheckedEmbedding([[1.0], [value]]),
                )

    def test_default_model_is_iteration_local_qwen_directory(self):
        self.assertEqual(
            Path(risk_retrieve.DEFAULT_MODEL),
            ROOT / "models" / "Qwen3-Embedding-0.6B",
        )
        self.assertEqual(
            risk_retrieve.MODEL_REPO_ID,
            "Qwen/Qwen3-Embedding-0.6B",
        )

    def test_real_backend_uses_qwen_query_prompt_and_document_encoding(self):
        captured = {}

        class FakeArray:
            def __init__(self, values):
                self.values = values

            def tolist(self):
                return self.values

        class FakeSentenceTransformer:
            def __init__(self, model_name, **kwargs):
                captured["model_name"] = model_name
                captured["init_kwargs"] = kwargs
                captured["encode_calls"] = []

            def encode(self, texts, **kwargs):
                captured["encode_calls"].append((texts, kwargs))
                if kwargs.get("prompt_name") == "query":
                    return FakeArray([[1.0, 0.0]])
                return FakeArray([[0.0, 1.0], [0.5, 0.5]])

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = FakeSentenceTransformer
        with mock.patch.dict(
            sys.modules,
            {"sentence_transformers": fake_module},
        ):
            backend = risk_retrieve.SentenceTransformerBackend("local-model")
            query_vector = backend.encode_query("query")
            document_vectors = backend.encode_documents(["doc-1", "doc-2"])

        self.assertEqual(query_vector, [1.0, 0.0])
        self.assertEqual(document_vectors, [[0.0, 1.0], [0.5, 0.5]])
        self.assertEqual(captured["model_name"], "local-model")
        self.assertEqual(captured["init_kwargs"], {"local_files_only": True})
        self.assertEqual(
            captured["encode_calls"],
            [
                (
                    ["query"],
                    {
                        "prompt_name": "query",
                        "normalize_embeddings": True,
                        "convert_to_numpy": True,
                    },
                ),
                (
                    ["doc-1", "doc-2"],
                    {
                        "normalize_embeddings": True,
                        "convert_to_numpy": True,
                    },
                ),
            ],
        )

    def test_query_embedding_must_return_one_vector(self):
        class FakeArray:
            def tolist(self):
                return []

        class FakeSentenceTransformer:
            def __init__(self, _model_name, **_kwargs):
                pass

            def encode(self, _texts, **_kwargs):
                return FakeArray()

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = FakeSentenceTransformer
        with mock.patch.dict(
            sys.modules,
            {"sentence_transformers": fake_module},
        ):
            backend = risk_retrieve.SentenceTransformerBackend("local-model")
            with self.assertRaisesRegex(RuntimeError, "数量不为 1"):
                backend.encode_query("query")

    def test_real_backend_wraps_query_and_document_failures(self):
        class FakeSentenceTransformer:
            def __init__(self, _model_name, **_kwargs):
                pass

            def encode(self, _texts, **kwargs):
                if kwargs.get("prompt_name") == "query":
                    raise ValueError("query failed")
                raise ValueError("document failed")

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = FakeSentenceTransformer
        with mock.patch.dict(
            sys.modules,
            {"sentence_transformers": fake_module},
        ):
            backend = risk_retrieve.SentenceTransformerBackend("local-model")
            with self.assertRaisesRegex(RuntimeError, "查询 Embedding"):
                backend.encode_query("query")
            with self.assertRaisesRegex(RuntimeError, "错题 Embedding"):
                backend.encode_documents(["doc"])


if __name__ == "__main__":
    unittest.main()
