import struct
import unittest

import protocol


class FrameDecoderTests(unittest.TestCase):
    def test_encoder_rejects_payload_over_wire_limit(self):
        protocol.encode_frame(protocol.T_ACK, 0, b"x" * protocol.MAX_PAYLOAD)
        with self.assertRaises(ValueError):
            protocol.encode_frame(protocol.T_ACK, 0, b"x" * (protocol.MAX_PAYLOAD + 1))

    def test_half_packets_and_sticky_packets(self):
        first = protocol.encode_frame(protocol.T_HELLO, 0, b"hello")
        second = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"audio")
        decoder = protocol.FrameDecoder()

        self.assertEqual(decoder.feed(first[:3]), [])
        self.assertEqual(decoder.feed(first[3:] + second), [
            (protocol.T_HELLO, 0, b"hello"),
            (protocol.T_AUDIO_CHUNK, 1, b"audio"),
        ])

    def test_bad_magic_has_no_associated_sequence(self):
        raw = bytearray(protocol.encode_frame(protocol.T_HELLO, 0))
        raw[0] ^= 0xFF

        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(raw)

        self.assertEqual(caught.exception.code, "BAD_MAGIC")
        self.assertEqual(caught.exception.seq, 0)

    def test_bad_crc_preserves_associated_sequence(self):
        raw = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 7, b"audio"))
        raw[-1] ^= 0xFF

        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(raw)

        self.assertEqual(caught.exception.code, "BAD_CRC")
        self.assertEqual(caught.exception.seq, 7)

    def test_oversized_payload_is_rejected_from_header_only(self):
        header = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 9, protocol.MAX_PAYLOAD + 1
        )

        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(header)

        self.assertEqual(caught.exception.code, "PAYLOAD_TOO_LARGE")
        self.assertEqual(caught.exception.seq, 9)

    def test_valid_frames_before_an_error_are_preserved(self):
        hello = protocol.encode_frame(protocol.T_HELLO, 0, b"hello")
        bad = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"audio"))
        bad[-1] ^= 0xFF

        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(hello + bad)

        self.assertEqual(caught.exception.code, "BAD_CRC")
        self.assertEqual(caught.exception.frames, (
            (protocol.T_HELLO, 0, b"hello"),
        ))


if __name__ == "__main__":
    unittest.main()
