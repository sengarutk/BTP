import os
import sys
import zipfile
import urllib.request

target_dir = "/home/sengar/BTP/uav-split-perception/datasets/coco128"
os.makedirs(target_dir, exist_ok=True)
images_dir = os.path.join(target_dir, "images")
labels_dir = os.path.join(target_dir, "labels")
os.makedirs(images_dir, exist_ok=True)
os.makedirs(labels_dir, exist_ok=True)

urls = [
    "https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip",
    "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip",
    "https://ultralytics.com/assets/coco128.zip",
]

zip_path = "/tmp/coco128.zip"
success = False
for url in urls:
    try:
        print(f"Trying URL: {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response, open(zip_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print(f"Downloaded {len(data)} bytes from {url}")
        success = True
        break
    except Exception as e:
        print(f"Failed from {url}: {e}")

if success:
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("/tmp/coco128_extracted")
    
    extracted_root = "/tmp/coco128_extracted/coco128"
    import shutil
    for root_subdir in ["images/train2017", "images", "images/val"]:
        src_img = os.path.join(extracted_root, root_subdir)
        if os.path.exists(src_img):
            for f in os.listdir(src_img):
                if f.endswith(('.jpg', '.png')):
                    shutil.copy(os.path.join(src_img, f), os.path.join(images_dir, f))
            break
            
    for root_subdir in ["labels/train2017", "labels", "labels/val"]:
        src_lbl = os.path.join(extracted_root, root_subdir)
        if os.path.exists(src_lbl):
            for f in os.listdir(src_lbl):
                if f.endswith('.txt'):
                    shutil.copy(os.path.join(src_lbl, f), os.path.join(labels_dir, f))
            break
    print("COCO128 successfully prepared. Total images:", len(os.listdir(images_dir)))
