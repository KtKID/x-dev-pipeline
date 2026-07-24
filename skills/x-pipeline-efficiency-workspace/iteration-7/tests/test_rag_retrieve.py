import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "x-dev-rag-call"
SCRIPT_DIR = SKILL / "scripts"
CATALOG = (
    ROOT
    / "skills"
    / "x-adversarial-risk"
    / "references"
    / "risk-mistakes.md"
)

sys.path.insert(0, str(SCRIPT_DIR))
import rag_retrieve  # noqa: E402


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


class RagRetrieveTest(unittest.TestCase):
    def run_main(self, args, vectors):
        output = io.StringIO()
        factory = lambda _model: FixedEmbedding(vectors)
        with contextlib.redirect_stdout(output):
            code = rag_retrieve.main(args, embedder_factory=factory)
        return code, json.loads(output.getvalue())

    def test_markdown_headings_form_five_risk_chunks(self):
        chunks = rag_retrieve.load_chunks(CATALOG)
        self.assertEqual(
            [chunk.id for chunk in chunks],
            [
                "A-risk-001",
                "A-risk-002",
                "A-risk-003",
                "A-risk-004",
                "A-risk-005",
            ],
        )
        self.assertTrue(all(chunk.text.startswith("## A-risk-") for chunk in chunks))

    def test_directory_reads_markdown_and_text(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw)
            (source / "one.md").write_text(
                "# Title\n\n## Card-A\n\nalpha",
                encoding="utf-8",
            )
            (source / "two.txt").write_text(
                "beta\n\n\ngamma",
                encoding="utf-8",
            )
            (source / "ignored.json").write_text("{}", encoding="utf-8")
            chunks = rag_retrieve.load_chunks(source)
        self.assertEqual(
            [chunk.id for chunk in chunks],
            ["Card-A", "two#001", "two#002"],
        )

    def test_top_one_returns_minimal_fields_without_score(self):
        chunks = rag_retrieve.load_chunks(CATALOG)
        vectors = [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.1, 0.9],
            [0.2, 0.8],
            [1.0, 0.0],
            [0.3, 0.7],
        ]
        code, payload = self.run_main(
            [
                "--source",
                str(CATALOG),
                "--query",
                "幂等请求失败后重试",
                "--top-n",
                "1",
                "--json",
            ],
            vectors,
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["matches"]), 1)
        self.assertEqual(payload["matches"][0]["id"], "A-risk-004")
        self.assertEqual(
            set(payload["matches"][0]),
            {"id", "source", "text"},
        )

    def test_top_n_larger_than_chunk_count_returns_all(self):
        chunks = rag_retrieve.load_chunks(CATALOG)
        matches = rag_retrieve.retrieve(
            chunks,
            "query",
            10,
            FixedEmbedding([[1.0], *([[1.0]] * len(chunks))]),
        )
        self.assertEqual(len(matches), len(chunks))

    def test_missing_source_returns_io_error_before_model_load(self):
        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "missing.md"
            output = io.StringIO()

            def fail_if_called(_model):
                raise AssertionError("路径失败时不应加载模型")

            with contextlib.redirect_stdout(output):
                code = rag_retrieve.main(
                    [
                        "--source",
                        str(missing),
                        "--query",
                        "query",
                        "--json",
                    ],
                    embedder_factory=fail_if_called,
                )
        self.assertEqual(code, 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["error"], "IO_ERROR")

    def test_default_model_uses_iteration_local_qwen(self):
        self.assertEqual(
            Path(rag_retrieve.DEFAULT_MODEL),
            ROOT / "models" / "Qwen3-Embedding-0.6B",
        )
        self.assertEqual(
            rag_retrieve.MODEL_REPO_ID,
            "Qwen/Qwen3-Embedding-0.6B",
        )

    def test_backend_uses_query_prompt_and_normalized_documents(self):
        captured = []

        class FakeArray:
            def __init__(self, values):
                self.values = values

            def tolist(self):
                return self.values

        class FakeSentenceTransformer:
            def __init__(self, model_name, **kwargs):
                captured.append(("init", model_name, kwargs))

            def encode(self, texts, **kwargs):
                captured.append(("encode", texts, kwargs))
                if kwargs.get("prompt_name") == "query":
                    return FakeArray([[1.0, 0.0]])
                return FakeArray([[0.0, 1.0]])

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = FakeSentenceTransformer
        with mock.patch.dict(
            sys.modules,
            {"sentence_transformers": fake_module},
        ):
            backend = rag_retrieve.SentenceTransformerBackend("local-model")
            self.assertEqual(backend.encode_query("query"), [1.0, 0.0])
            self.assertEqual(backend.encode_documents(["doc"]), [[0.0, 1.0]])

        self.assertEqual(
            captured,
            [
                ("init", "local-model", {"local_files_only": True}),
                (
                    "encode",
                    ["query"],
                    {
                        "prompt_name": "query",
                        "normalize_embeddings": True,
                        "convert_to_numpy": True,
                    },
                ),
                (
                    "encode",
                    ["doc"],
                    {
                        "normalize_embeddings": True,
                        "convert_to_numpy": True,
                    },
                ),
            ],
        )


class RagSkillContractTest(unittest.TestCase):
    def test_skill_defines_llm_python_split_and_live_vectors(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: x-dev-rag-call", text)
        self.assertIn("LLM 负责", text)
        self.assertIn("Python 脚本负责", text)
        self.assertIn("--source", text)
        self.assertIn("--query", text)
        self.assertIn("--top-n", text)
        self.assertIn("每次调用实时计算向量", text)
        self.assertIn("无需按 ID 再次读取文件", text)
        self.assertIn("输出省略相似度分数", text)


if __name__ == "__main__":
    unittest.main()
