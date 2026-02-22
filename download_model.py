import os
import urllib.request
import zipfile
import sys

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_ZIP = "vosk-model-small-en-us-0.15.zip"
EXTRACT_DIR = "model"

def report_hook(count, block_size, total_size):
    if total_size > 0:
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownloading model... {percent}%")
        sys.stdout.flush()

def main():
    if not os.path.exists(EXTRACT_DIR):
        print(f"Downloading model from {MODEL_URL}...")
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP, reporthook=report_hook)
            print("\nDownload complete. Extracting...")
            with zipfile.ZipFile(MODEL_ZIP, 'r') as zip_ref:
                zip_ref.extractall(".")
            print("Extraction complete.")
            
            # The zip extracts to a folder named 'vosk-model-small-en-us-0.15'
            # Let's rename it to 'model'
            extracted_folder = "vosk-model-small-en-us-0.15"
            if os.path.exists(extracted_folder):
                os.rename(extracted_folder, EXTRACT_DIR)
            
            # Clean up the zip file
            if os.path.exists(MODEL_ZIP):
                os.remove(MODEL_ZIP)
                
            print(f"Model successfully saved to {EXTRACT_DIR}/")
        except Exception as e:
            print(f"\nError downloading/extracting model: {e}")
    else:
        print("Model already exists.")

if __name__ == "__main__":
    main()
