"""Fail the release gate if the mandatory GIS JUnit suite is empty/skipped/failing."""

import sys
import xml.etree.ElementTree as ET


def check(path):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    if len(cases) < 5 or any(
        item.find(tag) is not None for item in cases for tag in ("skipped", "error", "failure")
    ):
        raise ValueError("GIS release gate requires at least five passing tests and zero skips")


if __name__ == "__main__":
    check(sys.argv[1])
