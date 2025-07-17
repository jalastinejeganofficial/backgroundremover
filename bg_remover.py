import io
import zipfile
from pathlib import Path
import streamlit as st
from PIL import Image
from rembg import remove
import uuid
from concurrent.futures import ThreadPoolExecutor
import time
import numpy as np

MAX_FILES = 10  # Increased limit with better performance
ALLOWED_TYPES = ["png", "jpg", "jpeg", "webp"]
MAX_IMAGE_SIZE_MB = 10
MB_TO_BYTES = 1024 * 1024

def setup_page():
    """Sets up the Streamlit page configuration."""
    st.set_page_config(
        page_title="Advanced Background Remover", 
        page_icon="✂️",
        layout="wide"
    )
    hide_streamlit_style()
    st.title("🎨 Advanced Background Remover")
    st.markdown("""
    Remove backgrounds from your images instantly. Add custom backgrounds or download transparent PNGs.
    """)

def hide_streamlit_style():
    """Hides default Streamlit styling and adds custom styles that work with dark theme."""
    st.markdown("""
    <style>
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}
        .stDownloadButton button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
        }
        [data-testid="stSidebar"] {
            background-color: #f0f2f6;
        }
        /* Dark theme compatibility */
        @media (prefers-color-scheme: dark) {
            [data-testid="stSidebar"] {
                background-color: #1e1e1e;
            }
            .stRadio > div > div {
                color: white;
            }
            .stRadio > div > div > div > div {
                color: white;
            }
            .stMarkdown {
                color: white;
            }
        }
    </style>
    """, unsafe_allow_html=True)

def initialize_session():
    """Initializes session variables."""
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = str(uuid.uuid4())
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "results" not in st.session_state:
        st.session_state.results = []

def display_sidebar():
    """Displays the sidebar controls."""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Background options
        bg_option = st.radio(
            "Background Options",
            ["Transparent", "Color", "Image"],
            index=0,
            help="Choose what to replace the background with"
        )
        
        bg_color = "#FFFFFF"
        bg_image = None
        
        if bg_option == "Color":
            bg_color = st.color_picker("Choose background color", "#FFFFFF")
        elif bg_option == "Image":
            bg_image_file = st.file_uploader(
                "Upload background image",
                type=ALLOWED_TYPES,
                key="bg_image_uploader"
            )
            if bg_image_file:
                bg_image = Image.open(bg_image_file).convert("RGB")
        
        st.markdown("---")
        st.markdown(f"### 📤 Upload Images (Max {MAX_FILES})")
        
        uploaded_files = st.file_uploader(
            "Choose images",
            type=ALLOWED_TYPES,
            accept_multiple_files=True,
            key=st.session_state.get("uploader_key", "file_uploader"),
        )
        
        if uploaded_files and len(uploaded_files) > MAX_FILES:
            st.warning(f"Maximum {MAX_FILES} files allowed. Only the first {MAX_FILES} will be processed.")
            uploaded_files = uploaded_files[:MAX_FILES]
        
        process_btn = st.button(
            "✨ Remove Backgrounds",
            disabled=st.session_state.processing or not uploaded_files,
            type="primary"
        )
        
        st.markdown("---")
        display_footer()
        
        return uploaded_files, bg_option, bg_color, bg_image, process_btn

def display_footer():
    """Displays a custom footer."""
    footer = """
    <div style="position: fixed; bottom: 0; left: 20px;">
        <p style="color: inherit;">Developed with ❤ by <a href="https://github.com/jalastinejeganofficial" target="_blank">@jalastinejegan</a></p>
    </div>
    """
    st.sidebar.markdown(footer, unsafe_allow_html=True)

def process_images_parallel(uploaded_files, bg_option, bg_color, bg_image):
    """Processes images in parallel using ThreadPoolExecutor."""
    st.session_state.processing = True
    st.session_state.results = []
    
    start_time = time.time()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def process_single_image(file):
        try:
            if len(file.getvalue()) > MAX_IMAGE_SIZE_MB * MB_TO_BYTES:
                return None, f"Image {file.name} exceeds {MAX_IMAGE_SIZE_MB}MB limit", None
            
            original = Image.open(file).convert("RGBA")
            result = remove_background(file.getvalue())
            
            if bg_option == "Color":
                result = add_color_background(result, bg_color)
            elif bg_option == "Image" and bg_image:
                result = add_image_background(result, bg_image)
                
            return original, result, file.name
        except Exception as e:
            return None, f"Error processing {file.name}: {str(e)}", None
    
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_single_image, file) for file in uploaded_files]
        
        for i, future in enumerate(futures):
            try:
                original, result, name = future.result()
                if original and result:
                    st.session_state.results.append((original, result, name))
                elif name:
                    st.warning(result)  # Display warning message
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")
            
            # Update progress
            progress = (i + 1) / len(futures)
            progress_bar.progress(progress)
            status_text.text(f"Processed {i + 1}/{len(uploaded_files)} images")
    
    processing_time = time.time() - start_time
    status_text.text(f"Completed in {processing_time:.2f} seconds!")
    st.session_state.processing = False
    progress_bar.empty()

def remove_background(image_bytes):
    """Removes the background from an image."""
    result = remove(image_bytes)
    return Image.open(io.BytesIO(result)).convert("RGBA")

def add_color_background(image, color):
    """Adds a solid color background to a transparent image."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    background = Image.new('RGBA', image.size, color)
    return Image.alpha_composite(background, image)

def add_image_background(foreground, background_img):
    """Adds an image background to a transparent foreground."""
    # Resize background to match foreground if needed
    if background_img.size != foreground.size:
        background_img = background_img.resize(foreground.size)
    
    background = background_img.convert('RGBA')
    return Image.alpha_composite(background, foreground)

def display_results():
    """Displays the processing results."""
    if not st.session_state.results:
        return
    
    st.markdown("## 🎨 Results")
    
    # Display image grid
    cols_per_row = 2
    for i in range(0, len(st.session_state.results), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, (original, result, name) in zip(cols, st.session_state.results[i:i+cols_per_row]):
            with col:
                st.image(original, caption=f"Original: {name}", use_container_width=True)
                st.image(result, caption=f"Result: {name}", use_container_width=True)
    
    # Download options
    st.markdown("---")
    st.markdown("## 📥 Download Options")
    
    if len(st.session_state.results) == 1:
        download_single_image(st.session_state.results[0])
    else:
        download_all_images()

def download_single_image(image_data):
    """Provides download button for a single image."""
    original, result, name = image_data
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="Download Original",
            data=image_to_bytes(original),
            file_name=f"original_{name}",
            mime=f"image/{Path(name).suffix[1:]}",
        )
    
    with col2:
        st.download_button(
            label="Download Result",
            data=image_to_bytes(result),
            file_name=f"{Path(name).stem}_nobg.png",
            mime="image/png",
        )

def download_all_images():
    """Provides download options for multiple images."""
    if st.button("Download All as ZIP"):
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for original, result, name in st.session_state.results:
                # Add original
                orig_bytes = image_to_bytes(original)
                zip_file.writestr(f"originals/{name}", orig_bytes)
                
                # Add result
                res_bytes = image_to_bytes(result)
                zip_file.writestr(f"results/{Path(name).stem}_nobg.png", res_bytes)
        
        st.download_button(
            label="Click to download ZIP",
            data=zip_buffer.getvalue(),
            file_name="background_removed_images.zip",
            mime="application/zip",
        )

def image_to_bytes(img):
    """Converts an Image object to bytes with optimization."""
    buf = io.BytesIO()
    
    if img.mode == 'RGBA':
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=85, optimize=True)
    
    return buf.getvalue()

def main():
    setup_page()
    initialize_session()
    uploaded_files, bg_option, bg_color, bg_image, process_btn = display_sidebar()
    
    if process_btn and uploaded_files:
        process_images_parallel(uploaded_files, bg_option, bg_color, bg_image)
    
    display_results()

if __name__ == "__main__":
    main()