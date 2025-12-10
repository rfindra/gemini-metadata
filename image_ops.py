# image_ops.py
import os
import re
import cv2
import subprocess
from PIL import Image, ImageStat

class StockPhotoOptimizer:
    def __init__(self):
        self.universal_blacklist = {
            "vector", "illustration", "drawing", "painting", 
            "generated", "ai generated", "render", "3d", "artwork", 
            "graphic", "clipart", "cartoon", "sketch", "digital art"
        }
        self.high_value_tech_tags = {"no people", "isolated", "white background", "copy space"}

    def analyze_technical_specs(self, image_path):
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                specs = {"tags": [], "context_str": ""}
                if width > height: specs["tags"].append("horizontal")
                elif height > width: specs["tags"].append("vertical")
                else: specs["tags"].append("square")
                
                if img.mode != 'RGB': img = img.convert('RGB')
                grayscale = img.convert("L")
                stat = ImageStat.Stat(grayscale)
                avg_brightness = stat.mean[0]

                if avg_brightness > 230:
                    specs["tags"].extend(["white background", "isolated", "high key"])
                    specs["context_str"] += " Note: The image has a clean white background, suitable for isolation."
                elif avg_brightness < 40:
                    specs["tags"].extend(["black background", "low key", "dark"])
                    specs["context_str"] += " Note: The image is low-key / dark."
                return specs
        except:
            return {"tags": [], "context_str": ""}

    def clean_and_optimize_tags(self, ai_keywords, technical_tags):
        if isinstance(ai_keywords, list): 
            ai_tokens = [str(t).strip().lower() for t in ai_keywords]
        else: 
            ai_tokens = [t.strip().lower() for t in (ai_keywords or "").split(",")]
        
        tech_tokens = [t.strip().lower() for t in technical_tags]
        seen = {}
        final_ordered_list = []

        def is_valid(t):
            t_clean = re.sub(r"[^a-z0-9\s-]", "", t).strip()
            if len(t_clean) < 2: return False
            if t_clean in self.universal_blacklist: return False
            if t_clean in {"photo", "image", "stock", "hd", "4k"}: return False
            return True

        for t in ai_tokens[:5]:
            if is_valid(t) and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in tech_tokens:
            if t in self.high_value_tech_tags and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in ai_tokens[5:]:
            if is_valid(t) and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in tech_tokens:
            if t not in seen and is_valid(t):
                final_ordered_list.append(t)
                seen[t] = True

        return final_ordered_list[:49]

def create_xmp_sidecar(path_without_ext, title, desc, keywords):
    try:
        rdf_keywords = "\n".join([f"<rdf:li>{k}</rdf:li>" for k in keywords])
        xmp_content = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:dc='http://purl.org/dc/elements/1.1/'>
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang='x-default'>{title}</rdf:li>
        </rdf:Alt>
      </dc:title>
      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang='x-default'>{desc}</rdf:li>
        </rdf:Alt>
      </dc:description>
      <dc:subject>
        <rdf:Bag>
          {rdf_keywords}
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""
        xmp_path = f"{path_without_ext}.xmp"
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        return xmp_path
    except:
        return None

def get_analysis_image_path(original_file_path):
    ext = os.path.splitext(original_file_path)[1].lower()
    temp_img_path = original_file_path + "_preview.jpg"
    if ext in ['.mp4', '.mov', '.avi', '.mkv']:
        try:
            cap = cv2.VideoCapture(original_file_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 0: cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2) 
            else: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(temp_img_path, frame)
                return temp_img_path
            return None
        except: return None
    elif ext in ['.eps', '.ai']:
        try:
            args = ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-dEPSCrop", "-r150", f"-sOutputFile={temp_img_path}", original_file_path]
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_img_path): return temp_img_path
            return None
        except: return None
    else: return original_file_path