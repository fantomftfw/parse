import io
import os
import tempfile
import traceback
from flask import Flask, request, jsonify, Response
from docling.document_converter import DocumentConverter

app = Flask(__name__)

# Initialize the converter (can be reused)
# Place initialization outside the request handler for efficiency
try:
    converter = DocumentConverter()
    print("Docling DocumentConverter initialized successfully.")
except Exception as e:
    print(f"FATAL: Error initializing DocumentConverter: {e}")
    traceback.print_exc()
    # If the converter fails to initialize, the service cannot process files.
    # We'll check for `None` in the request handler.
    converter = None

@app.route('/process', methods=['POST'])
def process_document():
    """
    Flask endpoint to process an uploaded file using docling.
    Expects a multipart/form-data request with a 'file' field.
    Processes ONLY THE FIRST PAGE of the PDF using pypdfium2 before docling.
    Returns the docling output as Markdown text.
    """
    if converter is None:
        print("Error: Docling converter was not initialized.")
        # 503 Service Unavailable might be more appropriate if it failed init
        return jsonify({"error": "Docling converter not initialized during startup"}), 503

    if 'file' not in request.files:
        print("Error: No 'file' part in the request.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    if file.filename == '':
        print("Error: No file selected.")
        return jsonify({"error": "No selected file"}), 400

    single_page_temp_file_path = None # Rename this back to temp_file_path or similar
    original_filename = file.filename

    try:
        # --- Read file into memory ---
        file_bytes = file.read()
        print(f"Received file: {original_filename}, size: {len(file_bytes)} bytes")

        # --- ADD Back: Save original file to temp file ---
        temp_file_path = None # Use this variable name
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(original_filename)[1]) as temp_file:
             temp_file.write(file_bytes)
             temp_file_path = temp_file.name
             print(f"Original file temporarily saved to: {temp_file_path}")

        # --- Docling Processing (Use original temp file path) ---
        if not temp_file_path:
             return jsonify({"error": "Internal error: Temp file path not set."}), 500

        print(f"Processing full PDF with docling: {temp_file_path}")
        result = converter.convert(source=temp_file_path) # Use original temp file path
        print(f"Docling conversion successful (processed full document).")

        # Export to Markdown
        markdown_output = result.document.export_to_markdown()
        print(f"Successfully exported full document to Markdown ({len(markdown_output)} chars). Returning response.")

        # Return Markdown content with appropriate mimetype
        return Response(markdown_output, mimetype='text/markdown')

    except Exception as e:
        # General error handling remains largely the same
        print(f"Error during docling processing for {original_filename}: {e}")
        traceback.print_exc() # Log the full error for debugging
        # Return a generic server error to the client
        return jsonify({"error": "Failed to process document with docling", "details": str(e)}), 500

    finally:
        # --- Cleanup (Clean up the original temp file) ---
        if temp_file_path and os.path.exists(temp_file_path): # Check temp_file_path
            try:
                os.remove(temp_file_path) # Remove temp_file_path
                print(f"Removed temporary file: {temp_file_path}") # Log temp_file_path
            except OSError as e:
                print(f"Error removing temporary file {temp_file_path}: {e}") # Log temp_file_path


if __name__ == '__main__':
    # Run Flask development server
    # Host '0.0.0.0' makes it accessible from other containers/machines on the network
    # Use port 5001 by default, common alternative to 5000
    port = int(os.environ.get('PORT', 5001))
    print(f"Starting Flask server on http://0.0.0.0:{port}")
    # debug=True enables auto-reloading and provides detailed error pages
    # Disable debug mode in production environments
    app.run(host='0.0.0.0', port=port, debug=True) 