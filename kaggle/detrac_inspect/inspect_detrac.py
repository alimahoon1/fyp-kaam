"""Print the layout of the UA-DETRAC Kaggle copy: annotation XML structure, class names, image counts."""
import collections
import glob
import os
import xml.etree.ElementTree as ET

R = "/kaggle/input/datasets/bratjay/ua-detrac-orig"
for sub in ["DETRAC-Train-Annotations-XML", "DETRAC-Test-Annotations-XML", "DETRAC-Images", "DETRAC-MOT-toolkit"]:
    for dp, dn, fn in os.walk(os.path.join(R, sub)):
        if dp.count(os.sep) - R.count(os.sep) <= 3:
            print(dp, "dirs", len(dn), "files", len(fn), sorted(dn)[:3], sorted(fn)[:3])
for split in ["Train", "Test"]:
    xmls = sorted(glob.glob(f"{R}/DETRAC-{split}-Annotations-XML/**/*.xml", recursive=True))
    print(split, "xml files", len(xmls))
    if xmls:
        print(open(xmls[0]).read(3000))
    types = collections.Counter()
    nframes = 0
    for x in xmls:
        root = ET.parse(x).getroot()
        for fr in root.iter("frame"):
            nframes += 1
        for a in root.iter("attribute"):
            types[a.get("vehicle_type")] += 1
    print(split, "annotated frames", nframes, "vehicle types", dict(types))
seqdirs = sorted(glob.glob(f"{R}/DETRAC-Images/DETRAC-Images/MVI_*"))
print("image sequences", len(seqdirs), "total images", sum(len(os.listdir(d)) for d in seqdirs))
