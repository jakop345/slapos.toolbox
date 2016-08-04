
import unittest
from slapos.systool import sublist

class TestSystool(unittest.TestCase):
  def test_sublist(self):
    assert sublist("ab", "b")
    assert sublist("ac", "b") == False


if __name__ == '__main__':
  unittest.main()
