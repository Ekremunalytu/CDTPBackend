import pypdf
import sys

def read_pdf(file_path):
    try:
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        print(f"--- Content of {file_path} ---")
        print(text)
        print("--------------------------------")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

if __name__ == "__main__":
    files = ["guncel-yonetim-plani (1)_kopyası.pdf"]
    for f in files:
        read_pdf(f)
