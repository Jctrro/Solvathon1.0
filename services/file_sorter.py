import os
import shutil

def sort_file(old_path, meta):

    new_dir = f"repository/{meta['semester']}/{meta['subject_code']}/unit_{meta['unit']}"
    os.makedirs(new_dir, exist_ok=True)

    filename = os.path.basename(old_path)
    new_path = f"{new_dir}/{filename}"

    shutil.move(old_path, new_path)

    return new_path