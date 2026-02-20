import pdfplumber

def extract_text(file_path):

    full_text = ""

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:   # ⭐ REMOVE [:2]
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    return full_text