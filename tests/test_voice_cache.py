"""Paid boundaries mocked: cache identity, edits, corruption and interruption regressions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import voice
import build
import tts_elevenlabs as api


def alignment(text):
    return {"characters": list(text), "character_start_times_seconds": [i / 10 for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) / 10 for i in range(len(text))]}


class DialogueTests(unittest.TestCase):
    """Two speakers with tags: voice per line, tags in the request only, one cache per voice."""
    SPEAKERS = {"boss": {"voice_id": "second-voice-id", "settings": {"stability": 0.3}}, "dev": {}}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.script = Path(self.temp.name) / "skit.md"
        self.script.write_text("### 1.1\nboss: {annoyed} {slowly} Who spent the [budget]?\ndev: {nervous} Not me.\n\ndev: Ask him.\n### 1.8\ndev: Tap like.\n")
        self.calls = []
        def synthesize(key, vid, model, text, previous, nxt, settings):
            self.calls.append((vid, text, settings))
            request = api.synthesis_request(vid, model, text, previous, nxt, settings)
            return json.dumps(request, sort_keys=True).encode(), alignment(text)
        for guard in (patch.object(voice, "VOICE", "clone-voice-id"), patch.object(voice, "MODEL", "eleven_v3"),
                      patch.object(voice, "SETTINGS", {}), patch.object(voice, "SAY", {}), patch.object(voice, "_SAY_RE", None),
                      patch.object(voice, "SPEAKERS", self.SPEAKERS), patch.object(api, "SPEAKERS", self.SPEAKERS),
                      patch.object(voice, "api_key", return_value="fixture-key"), patch.object(voice, "synthesize", side_effect=synthesize)):
            guard.start()
            self.addCleanup(guard.stop)

    def run_voice(self):
        with patch.object(sys, "argv", ["voice.py", str(self.script)]):
            voice.main()

    def test_lines_are_split_by_speaker_without_a_blank_line(self):
        got = [(p["who"], p["tags"], p["text"], p["triggers"]) for p in voice.paragraphs(self.script)]
        self.assertEqual(got, [("boss", ["annoyed", "slowly"], "Who spent the budget?", ["budget"]), ("dev", ["nervous"], "Not me.", []),
                               ("dev", [], "Ask him.", []), ("dev", [], "Tap like.", [])])

    def test_each_line_goes_to_its_voice_with_tags_and_settings(self):
        self.run_voice()
        self.assertEqual(self.calls[0], ("second-voice-id", "[annoyed] [slowly] Who spent the budget?", {"stability": 0.3}))
        self.assertEqual(self.calls[1], ("clone-voice-id", "[nervous] Not me.", None))

    def test_tags_are_cut_from_spoken_text_and_timing(self):
        self.run_voice()
        paras = voice.paragraphs(self.script)
        meta = voice.cached_paragraph(self.script, paras[0], paras)
        self.assertEqual(meta["spoken"], "Who spent the budget?")
        self.assertEqual("".join(meta["alignment"]["characters"]), "Who spent the budget?")
        words = build.words_from(meta["alignment"], 0)
        self.assertEqual(words[0]["w"], "Who")
        self.assertEqual(words[0]["s"], len("[annoyed] [slowly] ") / 10)

    def test_changing_one_voice_revoices_only_that_speaker(self):
        self.run_voice()
        self.calls.clear()
        self.run_voice()
        self.assertEqual(self.calls, [])
        other = {**self.SPEAKERS, "boss": {"voice_id": "third-voice-id", "settings": {"stability": 0.3}}}
        with patch.object(voice, "SPEAKERS", other):
            self.run_voice()
        self.assertEqual([c[0] for c in self.calls], ["third-voice-id"])

    def test_changing_a_tag_revoices_only_that_line(self):
        self.run_voice()
        self.calls.clear()
        self.script.write_text(self.script.read_text().replace("{nervous}", "{calm}"))
        self.run_voice()
        self.assertEqual([c[1] for c in self.calls], ["[calm] Not me."])

    def test_mistakes_stop_before_any_paid_request(self):
        for text in ("### 1.1\nmanager: {angry} Text\n", "### 1.1\nboss: Text {angry} more\n", "### 1.1\nboss: Text\n\nmanager: Text\n"):
            self.script.write_text(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "speaker"):
                self.run_voice()
        self.assertEqual(self.calls, [])

    def test_tags_need_a_model_that_performs_them(self):
        with patch.object(voice, "MODEL", "eleven_multilingual_v2"), self.assertRaisesRegex(ValueError, "eleven_v3"):
            self.run_voice()
        self.assertEqual(self.calls, [])

    def test_tag_outside_the_timing_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "start of the timing"):
            voice.cut_prefix(alignment("Text"), "[calm] ")

    def test_plain_narration_is_untouched(self):
        self.script.write_text("### 1.1\nWarning: this line has a colon.\n")
        self.assertEqual(voice.paragraphs(self.script)[0]["text"], "Warning: this line has a colon.")
        self.assertIsNone(voice.paragraphs(self.script)[0]["who"])


class VoiceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.script = Path(self.temp.name) / "batch.md"
        self.script.write_text("### 1.0\nSlate\n### 1.1\nAlpha\n\nBeta\n\nGamma\n\nDelta\n### 1.8\nLike\n### 1.9\nFollow\n### 2.1\nOther\n### 2.8\nEnd\n")
        self.calls = []
        def synthesize(key, vid, model, text, previous, nxt, settings):
            request = api.synthesis_request(vid, model, text, previous, nxt, settings)
            self.calls.append(request)
            return json.dumps(request, sort_keys=True).encode(), alignment(text)
        for guard in (patch.object(voice, "VOICE", "fixture-voice-id"),
                      patch.object(voice, "SETTINGS", {}), patch.object(voice, "SAY", {}),
                      patch.object(voice, "_SAY_RE", None), patch.object(voice, "api_key", return_value="fixture-key"),
                      patch.object(voice, "synthesize", side_effect=synthesize)):
            guard.start()
            self.addCleanup(guard.stop)

    def run_voice(self, only=None):
        with patch.object(sys, "argv", ["voice.py", str(self.script)] + ([only] if only else [])):
            voice.main()

    def test_unchanged_hit_needs_no_credentials_or_api(self):
        self.run_voice()
        with patch.object(voice, "api_key", side_effect=AssertionError("no credentials")), \
                patch.object(voice, "synthesize", side_effect=AssertionError("no API")):
            self.run_voice()

    def test_changed_neighbour_invalidates_adjacent_context(self):
        self.run_voice()
        self.calls.clear()
        self.script.write_text(self.script.read_text().replace("Beta", "Changed"))
        self.run_voice()
        self.assertEqual([r["body"]["text"] for r in self.calls], ["Alpha", "Changed", "Gamma"])

    def test_insertion_reuses_unchanged_requests_even_if_indices_move(self):
        self.run_voice()
        self.calls.clear()
        self.script.write_text(self.script.read_text().replace("Beta\n\nGamma", "Beta\n\nInserted\n\nGamma"))
        self.run_voice()
        self.assertEqual([r["body"]["text"] for r in self.calls], ["Beta", "Inserted", "Gamma"])
        meta = voice.cached_paragraph(self.script, {"block": "1.1", "para": 4})
        self.assertEqual(meta["spoken"], "Delta")

    def test_subset_preserves_full_context_and_other_audio(self):
        self.run_voice("1")
        self.assertTrue(all(r["body"]["text"] not in ("Slate", "Other", "End") for r in self.calls))
        self.calls.clear()
        self.run_voice("2")
        self.assertEqual([r["body"]["text"] for r in self.calls], ["Other", "End"])
        self.assertEqual(voice.cached_paragraph(self.script, {"block": "1.1", "para": 0})["spoken"], "Alpha")

    def test_full_voice_id_settings_language_model_invalidate(self):
        self.run_voice()
        for target, attr, value in ((voice, "VOICE", "fixtur-another-voice"),
                                    (voice, "MODEL", "eleven_multilingual_v2"),
                                    (voice, "SETTINGS", {"stability": 0.2}), (api, "LANG", "fr")):
            with self.subTest(attr=attr), patch.object(target, attr, value):
                self.calls.clear()
                self.run_voice()
                self.assertEqual(len(self.calls), 8)

    def test_endings_follow_body_without_cross_ending_context(self):
        ps = voice.paragraphs(self.script)
        for i, p in enumerate(ps):
            if p["block"] in ("1.8", "1.9"):
                body = voice.request_for(ps, i)["body"]
                self.assertEqual(body["previous_text"], "Delta")
                self.assertNotIn("next_text", body)

    def test_corrupt_audio_json_and_alignment_are_not_hits(self):
        self.run_voice()
        directory = voice.tts_dir(self.script)
        ps = voice.paragraphs(self.script)
        request = voice.request_for(ps, 0)
        path = directory / "cache" / voice.request_key(request)
        for corrupt in ("audio", "json", "alignment", "nan", "checksum", "legacy"):
            with self.subTest(corrupt=corrupt):
                self.run_voice()
                mp3, js = path.with_suffix(".mp3"), path.with_suffix(".json")
                meta = json.loads(js.read_text())
                if corrupt == "audio":
                    mp3.write_bytes(b"truncated")
                elif corrupt == "json":
                    js.write_text("{")
                else:
                    if corrupt == "alignment": meta["alignment"]["characters"] = ["x"]
                    if corrupt == "nan": meta["alignment"]["character_start_times_seconds"][0] = float("nan")
                    if corrupt == "checksum": meta.pop("audio_sha256")
                    if corrupt == "legacy": meta.pop("request")
                    js.write_text(json.dumps(meta))
                # Remove valid indexed copies: otherwise they correctly repair the shared cache.
                (directory / "1.1-0.mp3").unlink()
                self.calls.clear()
                self.run_voice()
                self.assertEqual([r["body"]["text"] for r in self.calls], ["Alpha"])

    def test_invalid_api_alignment_never_published(self):
        with patch.object(voice, "synthesize", return_value=(b"audio", alignment("wrong"))):
            with self.assertRaisesRegex(ValueError, "invalid character timing"):
                self.run_voice()
        self.assertFalse((voice.tts_dir(self.script) / "1.1-0.json").exists())

    def test_interrupted_generation_keeps_mapping_and_cached_work(self):
        self.run_voice()
        old = (voice.tts_dir(self.script) / "paragraphs.json").read_bytes()
        self.script.write_text(self.script.read_text().replace("Beta", "Changed"))
        with patch.object(voice, "synthesize", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.run_voice()
        self.assertEqual((voice.tts_dir(self.script) / "paragraphs.json").read_bytes(), old)

    def test_build_refuses_stale_index_before_audio_decode(self):
        self.run_voice()
        self.script.write_text(self.script.read_text().replace("Beta", "Changed"))
        ps = voice.paragraphs(self.script)
        with patch.object(build, "load_audio", side_effect=AssertionError("must validate first")):
            with self.assertRaisesRegex(ValueError, "stale voice"):
                build.tts_audio(voice.tts_dir(self.script), self.script, ps)(ps[0])

    def test_request_metadata_equals_real_api_payload(self):
        class Response:
            ok = True
            headers = {}
            def json(self):
                return {"audio_base64": "YQ==", "alignment": alignment("Hello")}
        req = api.synthesis_request("fixture", "eleven_v3", "Hello", "Before", "After", {"stability": 0.2})
        with patch.object(api, "post", return_value=Response()) as post:
            api.synthesize("fake", "fixture", "eleven_v3", "Hello", "Before", "After", {"stability": 0.2})
        self.assertEqual(post.call_args.kwargs["json"], req["body"])
        self.assertEqual(post.call_args.kwargs["params"], req["params"])


if __name__ == "__main__":
    unittest.main()
