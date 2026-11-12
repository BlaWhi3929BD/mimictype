import unittest
from mimictype.core.normalizer import TextNormalizer


class TestTextNormalizer(unittest.TestCase):

    def test_smart_quotes(self):
        text = "«Привет», — сказал он: “Hello world”"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, '"Привет", -- сказал он: "Hello world"')

    def test_single_smart_quotes(self):
        text = "It’s a ‘test’"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, "It's a 'test'")

    def test_dashes(self):
        text = "word1—word2–word3−word4"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, "word1--word2-word3-word4")

    def test_non_breaking_spaces(self):
        text = "Hello\u00a0World\u2003test"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, "Hello World test")

    def test_zero_width_chars(self):
        text = "Zero\u200bWidth\ufeffSpace"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, "ZeroWidthSpace")

    def test_newline_normalization(self):
        text = "line1\r\nline2\rline3\nline4"
        normalized = TextNormalizer.normalize(text)
        self.assertEqual(normalized, "line1\nline2\nline3\nline4")

    def test_kazakh_letters(self):
        text = "Сәлем әлем"
        # When preserve_kazakh is False, translates to standard Russian letters
        normalized = TextNormalizer.normalize(text, preserve_kazakh=False)
        self.assertEqual(normalized, "Салем алем")

        # When preserve_kazakh is True, leaves intact
        preserved = TextNormalizer.normalize(text, preserve_kazakh=True)
        self.assertEqual(preserved, "Сәлем әлем")


if __name__ == "__main__":
    unittest.main()
