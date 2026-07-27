import io
import struct
import unittest
import wave

import audio


def make_wav(pcm=b"\x00\x01\x02\x03", rate=16000, channels=1, width=2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(pcm)
    return stream.getvalue()


class WavTests(unittest.TestCase):
    def test_supported_wav_returns_pcm_only(self):
        self.assertEqual(audio.wav_pcm(make_wav()), b"\x00\x01\x02\x03")

    def test_unknown_odd_sized_chunk_is_skipped_with_padding(self):
        original = make_wav()
        extra = b"JUNK" + struct.pack("<I", 1) + b"x\x00"
        changed = original[:12] + extra + original[12:]
        changed = changed[:4] + struct.pack("<I", len(changed) - 8) + changed[8:]

        self.assertEqual(audio.wav_pcm(changed), b"\x00\x01\x02\x03")

    def test_unsupported_format_and_truncation_fail(self):
        for wav in (
            make_wav(rate=8000),
            make_wav(channels=2, pcm=b"\x00" * 8),
            make_wav(width=1),
            make_wav()[:-1],
            b"not wav",
        ):
            with self.subTest(length=len(wav)):
                with self.assertRaises(ValueError):
                    audio.wav_pcm(wav)

    def test_chunk_pcm_has_configured_boundaries(self):
        self.assertEqual(list(audio.chunk_pcm(b"abcdef", 4)), [b"abcd", b"ef"])


if __name__ == "__main__":
    unittest.main()
