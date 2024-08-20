# IKEA 3D Model Batch Downloader

This script batch downloads 3D model files (GLB format) from IKEA product pages, which you can open in 3D software like Blender. It has been tested only on the Finnish IKEA website (https://www.ikea.com/fi/en).

## Installation

1. Install Python:
   - Download Python 3.7 or later from [python.org](https://www.python.org/downloads/)
   - During installation, make sure to check the box that says "Add Python to PATH"

2. Download the script:
   - Download `ikea-glb-downloader.py` from this repository
   - Save it to a folder of your choice (e.g., `C:\IKEA-Downloader`)

3. Install required packages:
   - Open the folder where you saved `ikea-glb-downloader.py`
   - Hold Shift and right-click in the folder, then select "Open PowerShell window here" or "Open command window here"
   - In the opened window, type the following command and press Enter:
     ```
     pip install requests beautifulsoup4 tqdm selenium webdriver_manager
     ```

## Usage

1. Run the script:
   - In the same folder as before, hold Shift and right-click, then select "Open PowerShell window here" or "Open command window here"
   - Type the following command and press Enter:
     ```
     python ikea-glb-downloader.py
     ```

2. Follow the prompts:
   - Enter the IKEA category URL when asked (e.g., https://www.ikea.com/fi/fi/cat/chairs-fu002/)
   - Choose whether to download all color variants by typing 'y' or 'n'

3. The script will:
   - Scrape product links from the provided category page
   - Extract 3D model URLs for each product
   - Download GLB files
   - Store product information in an SQLite database

Downloaded files are saved in the `downloaded-files` directory within the script's folder.

## Additional Information

- The script won't download the same file twice, even if run multiple times
- You can run the script again with different category URLs to download more 3D models
- If you encounter any issues, make sure you have a stable internet connection and try running the script again
