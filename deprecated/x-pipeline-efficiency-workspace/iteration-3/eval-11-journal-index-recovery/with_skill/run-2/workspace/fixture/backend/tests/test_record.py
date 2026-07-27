from __future__ import annotations

import json
import unittest
import zlib

from fixture.backend.record import RecordError, decode_record, encode_record


class RecordCodecTests(unittest.TestCase):
    def payload(self) -> dict[str, object]:
        return {
            "expected_version": 0,
            "key": "alpha",
            "op": "put",
            "request_id": "r-1",
            "seq": 1,
            "value": "A",
        }

    def test_encode_is_canonical_and_crc_is_reproducible(self) -> None:
        payload = self.payload()
        expected_crc = f"{zlib.crc32(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')) & 0xFFFFFFFF:08x}"

        raw = encode_record(payload)
        decoded_json = json.loads(raw)

        self.assertEqual(raw.count(b"\n"), 1)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(decoded_json["crc32"], expected_crc)
        self.assertEqual(decode_record(raw), {"crc32": expected_crc, **payload})

    def test_delete_requires_null_and_round_trips(self) -> None:
        payload = self.payload() | {"op": "delete", "value": None}
        self.assertEqual(decode_record(encode_record(payload))["value"], None)

    def test_rejects_invalid_shape_type_crc_and_line_boundary(self) -> None:
        valid = encode_record(self.payload())
        cases: list[bytes] = [
            valid[:-1],
            valid + b"\n",
            valid.replace(b'"seq":1', b'"seq":true'),
            valid.replace(b'"value":"A"', b'"value":null'),
            valid.replace(b'"crc32":"', b'"extra":1,"crc32":"'),
            valid.replace(b'"crc32":"', b'"crc32":"0'),
            b"\xff\n",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(RecordError):
                    decode_record(raw)

    def test_encode_rejects_negative_versions_and_extra_fields(self) -> None:
        with self.assertRaises(RecordError):
            encode_record(self.payload() | {"expected_version": -1})
        with self.assertRaises(RecordError):
            encode_record(self.payload() | {"extra": "x"})

    def test_non_string_operation_always_raises_record_error(self) -> None:
        for operation in ([], {}, 1, None):
            with self.subTest(operation=operation):
                payload = self.payload() | {"op": operation}
                with self.assertRaises(RecordError):
                    encode_record(payload)

                canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                record = {"crc32": f"{zlib.crc32(canonical) & 0xFFFFFFFF:08x}", **payload}
                raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
                with self.assertRaises(RecordError):
                    decode_record(raw)


if __name__ == "__main__":
    unittest.main()
