"""Turn pytest JUnit XML failures into GitHub Actions error annotations (readable through the API)."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
count = 0
for case in root.iter("testcase"):
    for tag in ("failure", "error"):
        node = case.find(tag)
        if node is None:
            continue
        text = (node.get("message", "") + "\n" + (node.text or ""))[-3000:]
        text = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title={case.get('classname')}.{case.get('name')}::{text}")
        count += 1
print(f"{count} failing test(s)")
