import unittest
from helpers import *


class TestLineParser(unittest.TestCase):
    def test_parse_movie(self):
        self.assertEqual(parse_movie_info("1945 From 2019"), ("1945 From", "2019"))
        self.assertEqual(parse_movie_info("Movie"), ("Movie", None))
        self.assertEqual(parse_movie_info("2018"), ("2018", None))
        self.assertEqual(parse_movie_info("Movie 2019"), ("Movie", "2019"))
        self.assertEqual(parse_movie_info("Movie (2019)"), ("Movie", "2019"))

    def test_clean_links(self):
        # print(clean_link("10x10.1080p.BluRay.mp4"))
        self.assertEqual(clean_link("Movie.1234.2018.BluRay.mp4"), "Movie 1234 2018")
        self.assertEqual(clean_link("Movie.2018.1080p.BluRay.mp4"), "Movie 2018")
        self.assertEqual(clean_link("10x10.1080p.BluRay.mp4"), "10x10")


if __name__ == "__main__":
    unittest.main()
