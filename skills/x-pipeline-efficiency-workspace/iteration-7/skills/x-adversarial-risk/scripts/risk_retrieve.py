#!/usr/bin/env python3
"""Retrieve adversarial-risk mistakes by normalized text embeddings."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Callable, Protocol, Sequence

from risk_contract import Issue, RiskCard, parse_catalog


MODEL_REPO_ID = "Qwen/Qwen3-Embedding-0.6B"
ITERATION_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = str(ITERATION_ROOT / "models" / "Qwen3-Embedding-0.6B")


class CliArgumentError(ValueError):
    """Represent an argparse failure without terminating the process."""


class RiskArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


class EmbeddingBackend(Protocol):
    def encode_query(self, text: str) -> Sequence[float]:
        """Return one normalized query vector."""

    def encode_documents(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        """Return one normalized document vector for every input text."""


class SentenceTransformerBackend:
    """Load an already available local Sentence Transformers model."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers 未安装；请先准备依赖和本地模型"
            ) from exc

        try:
            self._model = SentenceTransformer(
                model_name,
                local_files_only=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"本地模型加载失败：{model_name}；程序已禁止联网下载"
            ) from exc

    def encode_query(self, text: str) -> Sequence[float]:
        try:
            vectors = self._model.encode(
                [text],
                prompt_name="query",
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise RuntimeError("查询 Embedding 计算失败") from exc
        values = vectors.tolist()
        if len(values) != 1:
            raise RuntimeError("查询 Embedding 返回的向量数量不为 1")
        return values[0]

    def encode_documents(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        try:
            vectors = self._model.encode(
                list(texts),
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise RuntimeError("错题 Embedding 计算失败") from exc
        return vectors.tolist()


def query_text(keywords: str, risk: str) -> str:
    return f"关键词：{keywords.strip()}\nRisk：{risk.strip()}"


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding 向量维度不一致或为空")
    score = sum(float(a) * float(b) for a, b in zip(left, right))
    if not math.isfinite(score):
        raise ValueError("Embedding 相似度不是有限数值")
    return score


def retrieve(
    cards: Sequence[RiskCard],
    keywords: str,
    risk: str,
    top_n: int,
    embedder: EmbeddingBackend,
) -> list[RiskCard]:
    if top_n < 1:
        raise ValueError("top-n 必须大于等于 1")
    if not keywords.strip():
        raise ValueError("keywords 不能为空")
    if not risk.strip():
        raise ValueError("risk 不能为空")
    if not cards:
        raise ValueError("错题集没有有效记录")

    query_vector = embedder.encode_query(query_text(keywords, risk))
    vectors = list(embedder.encode_documents([card.text for card in cards]))
    if len(vectors) != len(cards):
        raise ValueError("Embedding 返回的向量数量与输入数量不一致")

    ranked = [
        (_dot(query_vector, vector), card)
        for card, vector in zip(cards, vectors)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [card for _, card in ranked[: min(top_n, len(ranked))]]


def _format_issues(issues: Sequence[Issue]) -> str:
    return "；".join(
        f"{issue.code}"
        + (f"@{issue.line}" if issue.line else "")
        + f": {issue.message}"
        for issue in issues
    )


def _emit_error(error: str, message: str, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {"error": error, "message": message},
                ensure_ascii=False,
            )
        )
    else:
        print(f"{error}: {message}")


def _emit_matches(cards: Sequence[RiskCard], as_json: bool) -> None:
    matches = [{"id": card.id, "text": card.text} for card in cards]
    if as_json:
        print(json.dumps({"matches": matches}, ensure_ascii=False))
        return
    for match in matches:
        print(f"{match['id']}\n{match['text']}")


def build_parser() -> argparse.ArgumentParser:
    parser = RiskArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=RiskArgumentParser,
    )
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--catalog", required=True)
    query_parser.add_argument("--keywords", required=True)
    query_parser.add_argument("--risk", required=True)
    query_parser.add_argument("--top-n", type=int, default=1)
    query_parser.add_argument("--model", default=DEFAULT_MODEL)
    query_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(
    argv: Sequence[str] | None = None,
    embedder_factory: Callable[[str], EmbeddingBackend] | None = None,
) -> int:
    argument_list = list(argv) if argv is not None else sys.argv[1:]
    as_json = "--json" in argument_list
    try:
        args = build_parser().parse_args(argument_list)
    except CliArgumentError as exc:
        _emit_error("INVALID_ARGUMENT", str(exc), as_json)
        return 2

    if args.top_n < 1 or not args.keywords.strip() or not args.risk.strip():
        if args.top_n < 1:
            message = "top-n 必须大于等于 1"
        elif not args.keywords.strip():
            message = "keywords 不能为空"
        else:
            message = "risk 不能为空"
        _emit_error("INVALID_ARGUMENT", message, args.as_json)
        return 2

    catalog_path = Path(args.catalog)
    try:
        if not catalog_path.is_file():
            raise OSError("目标不是可读文件")
        catalog_text = catalog_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _emit_error("IO_ERROR", f"{catalog_path}: {exc}", args.as_json)
        return 2

    cards, issues = parse_catalog(catalog_text)
    if issues or not cards:
        message = _format_issues(issues) if issues else "错题集没有有效记录"
        _emit_error("INVALID_CATALOG", message, args.as_json)
        return 1

    factory = embedder_factory or SentenceTransformerBackend
    try:
        embedder = factory(args.model)
    except Exception as exc:
        _emit_error("MODEL_ERROR", str(exc), args.as_json)
        return 2

    try:
        matches = retrieve(
            cards=cards,
            keywords=args.keywords,
            risk=args.risk,
            top_n=args.top_n,
            embedder=embedder,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        _emit_error("EMBEDDING_ERROR", str(exc), args.as_json)
        return 2

    _emit_matches(matches, args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
